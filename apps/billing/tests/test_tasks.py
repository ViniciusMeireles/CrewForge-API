from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from apps.accounts.factories.organizations import OrganizationFactory
from apps.audit.choices import AuditActionChoices
from apps.audit.models.audit_event import AuditEvent
from apps.billing import tasks
from apps.billing.factories.payments import BillingProfileFactory, GatewayEventFactory
from apps.billing.factories.plans import PlanFactory
from apps.billing.models.gateway_event import GatewayEvent
from apps.billing.models.invoice import Invoice
from apps.billing.models.subscription import Subscription
from apps.billing.payments import cancel, change_plan
from apps.billing.tests.helpers import FakeGatewayMixin, free_plan, make_paid, pro_plan
from apps.teams.factories.teams import TeamFactory


def trialing(organization, ends_in: timedelta) -> Subscription:
    subscription = Subscription.objects.get(organization=organization)
    subscription.plan = pro_plan()
    subscription.status = 'trialing'
    subscription.trial_ends_at = timezone.now() + ends_in
    subscription.save()
    return subscription


class ExpireTrialsTestCase(FakeGatewayMixin, TestCase):
    def test_past_trial_moves_to_free(self):
        organization = OrganizationFactory()
        TeamFactory.create_batch(3, organization=organization)
        subscription = trialing(organization, timedelta(minutes=-1))
        self.assertEqual(tasks.expire_trials(), 1)
        subscription.refresh_from_db()
        self.assertEqual(
            (subscription.plan, subscription.status), (free_plan(), 'active')
        )
        self.assertIsNone(subscription.trial_ends_at)
        self.assertEqual(organization.teams.filter(is_active=True).count(), 3)
        event = AuditEvent.objects.get(
            action=AuditActionChoices.BILLING_SUBSCRIPTION_PLAN_CHANGED
        )
        self.assertEqual(event.metadata['reason'], 'trial_ended')

    def test_future_trial_untouched(self):
        subscription = trialing(OrganizationFactory(), timedelta(days=2))
        self.assertEqual(tasks.expire_trials(), 0)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, 'trialing')

    def test_pending_change_survives(self):
        organization = OrganizationFactory()
        BillingProfileFactory(organization=organization)
        trialing(organization, timedelta(days=2))
        change_plan(organization, pro_plan(), 'monthly')
        Subscription.objects.filter(organization=organization).update(
            trial_ends_at=timezone.now() - timedelta(minutes=1)
        )
        tasks.expire_trials()
        subscription = Subscription.objects.get(organization=organization)
        self.assertEqual(subscription.plan, free_plan())
        self.assertEqual(subscription.pending_plan, pro_plan())


class TrialRemindersTestCase(FakeGatewayMixin, TestCase):
    def test_one_email_per_mark(self):
        organization = OrganizationFactory()
        subscription = trialing(organization, timedelta(days=2, hours=12))
        with mock.patch('apps.billing.emails.queue_billing_email') as queue:
            self.assertEqual(tasks.send_trial_reminders(), 1)
            self.assertEqual(tasks.send_trial_reminders(), 0)
            subscription.trial_ends_at = timezone.now() + timedelta(hours=20)
            subscription.save()
            self.assertEqual(tasks.send_trial_reminders(), 1)
            self.assertEqual(tasks.send_trial_reminders(), 0)
        self.assertEqual(queue.call_count, 2)
        self.assertEqual(queue.call_args.args[0], 'TrialEndingEmail')

    def test_far_trial_gets_nothing(self):
        trialing(OrganizationFactory(), timedelta(days=10))
        self.assertEqual(tasks.send_trial_reminders(), 0)


class PeriodEndTestCase(FakeGatewayMixin, TestCase):
    def test_scheduled_downgrade_applied(self):
        organization = OrganizationFactory()
        cheap = PlanFactory(
            code='starter',
            monthly_price=Decimal('49.00'),
            annual_price=Decimal('490.00'),
        )
        make_paid(organization)
        change_plan(organization, cheap, 'monthly')
        Subscription.objects.filter(organization=organization).update(
            current_period_end=timezone.now() - timedelta(minutes=1)
        )
        self.assertEqual(tasks.apply_period_end(), 1)
        subscription = Subscription.objects.get(organization=organization)
        self.assertEqual(subscription.plan, cheap)
        self.assertIsNone(subscription.scheduled_plan)
        self.assertGreater(subscription.current_period_end, timezone.now())

    def test_cancel_moves_to_free(self):
        organization = OrganizationFactory()
        make_paid(organization)
        cancel(organization)
        Subscription.objects.filter(organization=organization).update(
            current_period_end=timezone.now() - timedelta(minutes=1)
        )
        with mock.patch('apps.billing.emails.queue_billing_email') as queue:
            tasks.apply_period_end()
        subscription = Subscription.objects.get(organization=organization)
        self.assertEqual((subscription.plan, subscription.cycle), (free_plan(), None))
        self.assertIsNone(subscription.current_period_end)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditActionChoices.BILLING_SUBSCRIPTION_CANCELED
            ).exists()
        )
        self.assertEqual(queue.call_args.args[0], 'SubscriptionCanceledEmail')

    def test_plain_renewal_rolls_the_period(self):
        organization = OrganizationFactory()
        make_paid(organization)
        Subscription.objects.filter(organization=organization).update(
            current_period_end=timezone.now() - timedelta(days=40)
        )
        tasks.apply_period_end()
        subscription = Subscription.objects.get(organization=organization)
        self.assertGreater(subscription.current_period_end, timezone.now())
        self.assertLess(subscription.current_period_start, timezone.now())


class ReconcileTestCase(FakeGatewayMixin, TestCase):
    def test_lost_payment_webhook_is_repaired(self):
        organization = OrganizationFactory()
        BillingProfileFactory(organization=organization)
        change_plan(organization, pro_plan(), 'monthly')
        invoice = Invoice.objects.get()
        self.fake_gateway.set_status(invoice.gateway_id, 'paid')
        result = tasks.reconcile()
        self.assertEqual(result['changed'], 1)
        self.assertEqual(
            Subscription.objects.get(organization=organization).status, 'active'
        )

    def test_unknown_recurring_payment_is_adopted(self):
        organization = OrganizationFactory()
        subscription = make_paid(organization)
        payment = self.fake_gateway.add_recurring(
            subscription.gateway_subscription_id, subscription.current_period_end.date()
        )
        tasks.reconcile()
        self.assertTrue(Invoice.objects.filter(gateway_id=payment.id).exists())

    def test_old_events_are_deleted(self):
        old = GatewayEventFactory()
        GatewayEvent.objects.filter(pk=old.pk).update(
            received_at=timezone.now()
            - timedelta(days=settings.BILLING_EVENT_RETENTION_DAYS + 1)
        )
        recent = GatewayEventFactory()
        tasks.reconcile()
        self.assertEqual(
            list(GatewayEvent.objects.values_list('pk', flat=True)), [recent.pk]
        )


class ScheduleTestCase(TestCase):
    def test_billing_beat_entries(self):
        names = {
            'billing-reconcile': 'apps.billing.tasks.reconcile_invoices',
            'billing-period-end': 'apps.billing.tasks.apply_period_end',
            'billing-expire-trials': 'apps.billing.tasks.expire_trials',
            'billing-trial-reminders': 'apps.billing.tasks.send_trial_reminders',
        }
        for key, task in names.items():
            with self.subTest(entry=key):
                self.assertEqual(settings.CELERY_BEAT_SCHEDULE[key]['task'], task)
