from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.audit.choices import AuditActionChoices
from apps.audit.models.audit_event import AuditEvent
from apps.billing.factories.payments import (
    VALID_CNPJ,
    BillingProfileFactory,
    InvoiceFactory,
)
from apps.billing.factories.plans import PlanFactory
from apps.billing.models.billing_profile import BillingProfile
from apps.billing.models.invoice import Invoice
from apps.billing.models.subscription import Subscription
from apps.billing.tests.helpers import FakeGatewayMixin, make_paid, pro_plan

PROFILE = {
    'legal_name': 'Acme Tecnologia Ltda',
    'tax_id': '11.222.333/0001-81',
    'email': 'billing@acme.com',
    'postal_code': '01001-000',
    'street': 'Rua das Flores',
    'number': '120',
    'complement': 'Sala 4',
    'district': 'Centro',
    'city': 'São Paulo',
    'state': 'SP',
}


class BillingTestCase(FakeGatewayMixin, APITestCaseMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.organization = OrganizationFactory()
        self.as_role(MemberRoleChoices.OWNER)

    def as_role(self, role):
        member = (
            self.organization.owner
            if role == MemberRoleChoices.OWNER
            else MemberFactory(organization=self.organization, role=role)
        )
        self.client.force_authenticate(member=member)
        return member

    @property
    def subscription(self) -> Subscription:
        return Subscription.objects.get(organization=self.organization)

    def post(self, name, data=None):
        return self.client.post(
            reverse(f'billing:{name}'), data=data or {}, format='json'
        )

    def events(self, action):
        return AuditEvent.objects.filter(
            organization_id=self.organization.pk, action=action
        )


class OwnerOnlyTestCase(BillingTestCase):
    def test_non_owners_cannot_write(self):
        writes = [
            ('subscription-change', {'plan': 'pro', 'cycle': 'monthly'}),
            ('subscription-cancel', None),
            ('subscription-resume', None),
            ('subscription-discard-change', None),
        ]
        for role in (
            MemberRoleChoices.ADMIN,
            MemberRoleChoices.MANAGER,
            MemberRoleChoices.MEMBER,
        ):
            self.as_role(role)
            for name, data in writes:
                with self.subTest(role=role, endpoint=name):
                    response = self.post(name, data)
                    self.assertEqual(
                        response.status_code, http_status.HTTP_403_FORBIDDEN
                    )
            with self.subTest(role=role, endpoint='profile PUT'):
                response = self.client.put(
                    reverse('billing:profile'), PROFILE, format='json'
                )
                self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
            with self.subTest(role=role, endpoint='preview'):
                response = self.client.get(
                    reverse('billing:subscription-preview'),
                    {'plan': 'pro', 'cycle': 'monthly'},
                )
                self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.gateway_state.calls, [])

    def test_inactive_owner_cannot_write(self):
        owner = self.organization.owner
        owner.is_active = False
        owner.save()
        self.client.force_authenticate(member=owner)
        response = self.post('subscription-change', {'plan': 'pro', 'cycle': 'monthly'})
        self.assertIn(
            response.status_code,
            {http_status.HTTP_401_UNAUTHORIZED, http_status.HTTP_403_FORBIDDEN},
        )
        self.assertEqual(self.gateway_state.calls, [])

    def test_manager_and_member_cannot_read(self):
        for role in (MemberRoleChoices.MANAGER, MemberRoleChoices.MEMBER):
            self.as_role(role)
            for name in ('profile', 'invoices'):
                with self.subTest(role=role, endpoint=name):
                    response = self.client.get(reverse(f'billing:{name}'))
                    self.assertEqual(
                        response.status_code, http_status.HTTP_403_FORBIDDEN
                    )

    def test_admin_reads_without_links_or_tax_id(self):
        BillingProfileFactory(organization=self.organization)
        InvoiceFactory(subscription=self.subscription)
        self.as_role(MemberRoleChoices.ADMIN)
        profile = self.client.get(reverse('billing:profile')).data
        self.assertIsNone(profile['tax_id'])
        self.assertEqual(profile['tax_id_masked'], 'CNPJ 11.222.333/0001-**')
        invoices = self.client.get(reverse('billing:invoices')).data['results']
        self.assertIsNone(invoices[0]['payment_url'])

    def test_session_exposes_billing_manage(self):
        response = self.client.get(reverse('accounts:session'))
        self.assertTrue(response.data['member']['access']['billing_manage'])
        self.as_role(MemberRoleChoices.ADMIN)
        response = self.client.get(reverse('accounts:session'))
        self.assertFalse(response.data['member']['access']['billing_manage'])
        self.assertTrue(response.data['member']['access']['billing'])


class ProfileTestCase(BillingTestCase):
    def test_get_before_any_save_is_404(self):
        response = self.client.get(reverse('billing:profile'))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')

    def test_put_saves_normalized_digits_and_audits_field_names(self):
        response = self.client.put(reverse('billing:profile'), PROFILE, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['tax_id'], VALID_CNPJ)
        self.assertEqual(response.data['postal_code'], '01001000')
        profile = BillingProfile.objects.get(organization=self.organization)
        self.assertEqual(profile.tax_id, VALID_CNPJ)
        event = self.events(AuditActionChoices.BILLING_PROFILE_UPDATED).get()
        self.assertIn('tax_id', event.metadata['fields'])
        self.assertNotIn(VALID_CNPJ, str(event.metadata))
        self.assertNotIn('billing@acme.com', str(event.metadata))

    def test_invalid_fields(self):
        cases = {
            'tax_id': ('12.345.678/0001-00', 'Enter a valid CPF or CNPJ.'),
            'email': ('not-an-email', 'Enter a valid email address.'),
            'postal_code': ('0100-100', 'Enter an 8-digit postal code.'),
        }
        for field, (value, message) in cases.items():
            with self.subTest(field=field):
                response = self.client.put(
                    reverse('billing:profile'), {**PROFILE, field: value}, format='json'
                )
                self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
                self.assertEqual(
                    str(response.data['error']['details'][field][0]), message
                )
        self.assertFalse(
            BillingProfile.objects.filter(organization=self.organization).exists()
        )

    def test_put_updates_the_gateway_customer(self):
        make_paid(self.organization)
        response = self.client.put(
            reverse('billing:profile'),
            {**PROFILE, 'legal_name': 'Acme SA'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            self.gateway_calls('upsert_customer'),
            [(self.subscription.gateway_customer_id,)],
        )

    def test_gateway_failure_keeps_the_old_profile(self):
        make_paid(self.organization)
        self.gateway_state.fail_next = True
        response = self.client.put(
            reverse('billing:profile'),
            {**PROFILE, 'legal_name': 'Acme SA'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data['error']['code'], 'GATEWAY_UNAVAILABLE')
        self.assertEqual(
            BillingProfile.objects.get(organization=self.organization).legal_name,
            'Acme Tecnologia Ltda',
        )


class PreviewTestCase(BillingTestCase):
    def preview(self, plan, cycle):
        return self.client.get(
            reverse('billing:subscription-preview'), {'plan': plan, 'cycle': cycle}
        )

    def test_new_from_trial(self):
        data = self.preview('pro', 'annual').data
        self.assertEqual(data['kind'], 'new')
        self.assertEqual(data['charged_now'], '990.00')
        self.assertEqual(data['recurring_amount'], '990.00')
        self.assertTrue(data['requires_billing_profile'])

    def test_ac12_upgrade(self):
        hundred = PlanFactory(
            code='team',
            monthly_price=Decimal('100.00'),
            annual_price=Decimal('1000.00'),
        )
        big = PlanFactory(
            code='business',
            monthly_price=Decimal('200.00'),
            annual_price=Decimal('2000.00'),
        )
        make_paid(self.organization, plan=hundred, days_left=15, period_days=30)
        data = self.preview(big.code, 'monthly').data
        self.assertEqual(data['kind'], 'upgrade')
        self.assertEqual(data['charged_now'], '50.00')
        self.assertEqual(data['recurring_amount'], '200.00')
        self.assertEqual(
            data['recurring_from'],
            self.subscription.current_period_end.date().isoformat(),
        )

    def test_downgrade_charges_nothing(self):
        cheap = PlanFactory(
            code='starter',
            monthly_price=Decimal('49.00'),
            annual_price=Decimal('490.00'),
        )
        make_paid(self.organization)
        data = self.preview(cheap.code, 'monthly').data
        self.assertEqual(data['kind'], 'downgrade')
        self.assertEqual(data['charged_now'], '0.00')

    def test_invalid_requests(self):
        make_paid(self.organization)
        hidden = PlanFactory(code='hidden', is_public=False)
        cases = [
            ('pro', 'monthly'),
            ('free', 'monthly'),
            (hidden.code, 'monthly'),
            ('pro', 'weekly'),
        ]
        for plan, cycle in cases:
            with self.subTest(plan=plan, cycle=cycle):
                response = self.preview(plan, cycle)
                self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)


class ChangeNewTestCase(BillingTestCase):
    def test_profile_required(self):
        response = self.post('subscription-change', {'plan': 'pro', 'cycle': 'monthly'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error']['code'], 'BILLING_PROFILE_REQUIRED')
        self.assertEqual(self.gateway_state.calls, [])

    def test_new_creates_a_pending_change(self):
        BillingProfileFactory(organization=self.organization)
        before = self.subscription
        response = self.post('subscription-change', {'plan': 'pro', 'cycle': 'annual'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('payment=return', response.data['payment_url'])
        subscription = self.subscription
        self.assertEqual(subscription.status, before.status)
        self.assertEqual(subscription.plan, before.plan)
        self.assertEqual(subscription.pending_plan, pro_plan())
        self.assertEqual(subscription.pending_cycle, 'annual')
        self.assertTrue(subscription.gateway_customer_id)
        self.assertTrue(subscription.gateway_subscription_id)
        invoice = Invoice.objects.get(subscription=subscription)
        self.assertEqual(
            (invoice.status, invoice.kind, invoice.amount),
            ('pending', 'recurring', Decimal('990.00')),
        )
        pending = response.data['subscription']['pending_change']
        self.assertEqual(pending['plan']['code'], 'pro')
        self.assertEqual(pending['payment_url'], response.data['payment_url'])

    def test_second_change_while_pending_is_409(self):
        BillingProfileFactory(organization=self.organization)
        self.post('subscription-change', {'plan': 'pro', 'cycle': 'annual'})
        response = self.post('subscription-change', {'plan': 'pro', 'cycle': 'monthly'})
        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
        self.assertEqual(len(self.gateway_calls('create_subscription')), 1)

    def test_retry_reuses_the_gateway_customer(self):
        BillingProfileFactory(organization=self.organization)
        state = self.gateway_state
        original = self.fake_gateway.create_subscription

        def fail_once(*args, **kwargs):
            from apps.billing.gateways.base import GatewayError

            if not getattr(fail_once, 'failed', False):
                fail_once.failed = True
                raise GatewayError('down')
            return original(*args, **kwargs)

        from unittest import mock

        with mock.patch(
            'apps.billing.gateways.fake.FakeGateway.create_subscription',
            side_effect=fail_once,
        ):
            first = self.post(
                'subscription-change', {'plan': 'pro', 'cycle': 'monthly'}
            )
            second = self.post(
                'subscription-change', {'plan': 'pro', 'cycle': 'monthly'}
            )
        self.assertEqual(first.status_code, http_status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(second.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(state.customers), 1)

    def test_gateway_failure_changes_nothing(self):
        BillingProfileFactory(organization=self.organization)
        self.gateway_state.fail_next = True
        response = self.post('subscription-change', {'plan': 'pro', 'cycle': 'monthly'})
        self.assertEqual(response.status_code, http_status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data['error']['code'], 'GATEWAY_UNAVAILABLE')
        subscription = self.subscription
        self.assertIsNone(subscription.pending_plan)
        self.assertEqual(subscription.gateway_customer_id, '')
        self.assertFalse(Invoice.objects.exists())


class ChangeUpgradeTestCase(BillingTestCase):
    def test_upgrade_applies_and_charges(self):
        hundred = PlanFactory(
            code='team',
            monthly_price=Decimal('100.00'),
            annual_price=Decimal('1000.00'),
        )
        big = PlanFactory(
            code='business',
            monthly_price=Decimal('200.00'),
            annual_price=Decimal('2000.00'),
        )
        make_paid(self.organization, plan=hundred)
        response = self.post(
            'subscription-change', {'plan': big.code, 'cycle': 'monthly'}
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data['payment_url'])
        subscription = self.subscription
        self.assertEqual(subscription.plan, big)
        invoice = Invoice.objects.get(subscription=subscription, kind='proration')
        self.assertEqual(invoice.amount, Decimal('50.00'))
        update = self.gateway_calls('update_subscription')[0]
        self.assertEqual(update[1:], (Decimal('200.00'), 'monthly', None))
        event = self.events(AuditActionChoices.BILLING_SUBSCRIPTION_PLAN_CHANGED).get()
        self.assertEqual(
            event.changes[0], {'field': 'plan', 'before': 'team', 'after': 'business'}
        )

    def test_monthly_to_annual_restarts_the_period(self):
        make_paid(self.organization, days_left=15)
        response = self.post('subscription-change', {'plan': 'pro', 'cycle': 'annual'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        subscription = self.subscription
        self.assertEqual(subscription.cycle, 'annual')
        self.assertGreater(
            subscription.current_period_end, timezone.now() + timedelta(days=360)
        )
        invoice = Invoice.objects.get(subscription=subscription, kind='proration')
        self.assertEqual(invoice.amount, Decimal('940.50'))

    def test_small_proration_is_not_charged(self):
        cheap = PlanFactory(
            code='team',
            monthly_price=Decimal('100.00'),
            annual_price=Decimal('1000.00'),
        )
        near = PlanFactory(
            code='team-plus',
            monthly_price=Decimal('104.00'),
            annual_price=Decimal('1040.00'),
        )
        make_paid(self.organization, plan=cheap)
        response = self.post(
            'subscription-change', {'plan': near.code, 'cycle': 'monthly'}
        )
        self.assertIsNone(response.data['payment_url'])
        self.assertFalse(Invoice.objects.filter(kind='proration').exists())
        self.assertEqual(self.subscription.plan, near)


class ChangeDowngradeTestCase(BillingTestCase):
    def test_downgrade_is_scheduled(self):
        cheap = PlanFactory(
            code='starter',
            monthly_price=Decimal('49.00'),
            annual_price=Decimal('490.00'),
        )
        make_paid(self.organization)
        response = self.post(
            'subscription-change', {'plan': cheap.code, 'cycle': 'monthly'}
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsNone(response.data['payment_url'])
        subscription = self.subscription
        self.assertEqual(subscription.plan, pro_plan())
        self.assertEqual(subscription.scheduled_plan, cheap)
        detail = response.data['subscription']
        self.assertEqual(detail['scheduled_change']['plan']['code'], 'starter')
        self.assertEqual(detail['next_charge']['amount'], '49.00')
        self.assertEqual(
            self.gateway_calls('update_subscription')[0][1], Decimal('49.00')
        )
        self.assertTrue(
            self.events(
                AuditActionChoices.BILLING_SUBSCRIPTION_CHANGE_SCHEDULED
            ).exists()
        )

    def test_undo_restores_the_gateway_value(self):
        cheap = PlanFactory(
            code='starter',
            monthly_price=Decimal('49.00'),
            annual_price=Decimal('490.00'),
        )
        make_paid(self.organization)
        self.post('subscription-change', {'plan': cheap.code, 'cycle': 'monthly'})
        response = self.post('subscription-resume')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsNone(response.data['scheduled_change'])
        self.assertEqual(
            self.gateway_calls('update_subscription')[-1][1], Decimal('99.00')
        )
        self.assertTrue(
            self.events(
                AuditActionChoices.BILLING_SUBSCRIPTION_CHANGE_CANCELED
            ).exists()
        )


class CancelResumeTestCase(BillingTestCase):
    def test_cancel_schedules_and_stops_future_charges(self):
        subscription = make_paid(self.organization)
        gateway_id = subscription.gateway_subscription_id
        response = self.post('subscription-cancel')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data['cancel_at_period_end'])
        self.assertIsNone(response.data['next_charge'])
        self.assertEqual(self.gateway_calls('delete_subscription'), [(gateway_id,)])
        self.assertEqual(self.subscription.gateway_subscription_id, '')
        self.assertTrue(
            self.events(
                AuditActionChoices.BILLING_SUBSCRIPTION_CANCEL_SCHEDULED
            ).exists()
        )

    def test_resume_before_period_end(self):
        subscription = make_paid(self.organization)
        self.post('subscription-cancel')
        response = self.post('subscription-resume')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['cancel_at_period_end'])
        created = self.gateway_calls('create_subscription')[-1]
        self.assertEqual(created[3], subscription.current_period_end.date())
        self.assertTrue(self.subscription.gateway_subscription_id)
        self.assertTrue(
            self.events(AuditActionChoices.BILLING_SUBSCRIPTION_RESUMED).exists()
        )

    def test_invalid_calls(self):
        self.assertEqual(
            self.post('subscription-cancel').status_code,
            http_status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.post('subscription-resume').status_code,
            http_status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.post('subscription-discard-change').status_code,
            http_status.HTTP_400_BAD_REQUEST,
        )
        make_paid(self.organization)
        self.post('subscription-cancel')
        self.assertEqual(
            self.post('subscription-cancel').status_code,
            http_status.HTTP_400_BAD_REQUEST,
        )


class DiscardChangeTestCase(BillingTestCase):
    def test_discard_deletes_the_pending_charge(self):
        BillingProfileFactory(organization=self.organization)
        self.post('subscription-change', {'plan': 'pro', 'cycle': 'monthly'})
        response = self.post('subscription-discard-change')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsNone(response.data['pending_change'])
        self.assertEqual(Invoice.objects.get().status, 'canceled')
        self.assertEqual(len(self.gateway_calls('delete_subscription')), 1)
        self.assertTrue(
            self.events(
                AuditActionChoices.BILLING_SUBSCRIPTION_CHANGE_CANCELED
            ).exists()
        )


class InvoiceListTestCase(BillingTestCase):
    def test_owner_lists_own_invoices_newest_first(self):
        subscription = self.subscription
        old = InvoiceFactory(
            subscription=subscription, issued_at=timezone.now() - timedelta(days=30)
        )
        new = InvoiceFactory(subscription=subscription)
        InvoiceFactory(
            subscription=Subscription.objects.get(organization=OrganizationFactory())
        )
        response = self.client.get(reverse('billing:invoices'))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            [row['id'] for row in response.data['results']], [new.pk, old.pk]
        )
        row = response.data['results'][0]
        self.assertEqual(row['description'], 'Monthly subscription')
        self.assertEqual(row['payment_url'], new.payment_url)

    def test_page_size_is_ten(self):
        InvoiceFactory.create_batch(11, subscription=self.subscription)
        response = self.client.get(reverse('billing:invoices'))
        self.assertEqual(response.data['count'], 11)
        self.assertEqual(len(response.data['results']), 10)


class SubscriptionDetailTestCase(BillingTestCase):
    def test_paid_detail(self):
        subscription = make_paid(self.organization)
        data = self.client.get(reverse('billing:subscription')).data
        self.assertEqual(data['cycle'], 'monthly')
        self.assertEqual(
            data['next_charge'],
            {
                'amount': '99.00',
                'date': subscription.current_period_end.date().isoformat(),
            },
        )
        self.assertTrue(data['billing_profile_complete'])
        self.assertIsNone(data['pending_change'])
        self.assertFalse(data['cancel_at_period_end'])

    def test_trial_detail(self):
        data = self.client.get(reverse('billing:subscription')).data
        self.assertIsNone(data['next_charge'])
        self.assertFalse(data['billing_profile_complete'])


class GatewayUndoTestCase(BillingTestCase):
    def test_failure_after_creating_the_gateway_subscription_deletes_it(self):
        BillingProfileFactory(organization=self.organization)
        from unittest import mock

        with (
            mock.patch(
                'apps.billing.payments.upsert_invoice', side_effect=RuntimeError('db')
            ),
            self.assertRaises(RuntimeError),
            self.assertLogs('apps.billing', 'ERROR') as logs,
        ):
            from apps.billing.payments import change_plan

            change_plan(self.organization, pro_plan(), 'monthly')
        created = self.gateway_calls('create_subscription')
        self.assertEqual(len(created), 1)
        self.assertEqual(len(self.gateway_calls('delete_subscription')), 1)
        self.assertEqual(self.gateway_state.subscriptions, {})
        self.assertNotIn('gateway_undo_failed', ''.join(logs.output))

    def test_failed_upgrade_restores_the_gateway_value(self):
        from unittest import mock

        from apps.billing.payments import change_plan

        hundred = PlanFactory(
            code='team',
            monthly_price=Decimal('100.00'),
            annual_price=Decimal('1000.00'),
        )
        big = PlanFactory(
            code='business',
            monthly_price=Decimal('200.00'),
            annual_price=Decimal('2000.00'),
        )
        subscription = make_paid(self.organization, plan=hundred)
        with (
            mock.patch(
                'apps.billing.payments.upsert_invoice', side_effect=RuntimeError('db')
            ),
            self.assertRaises(RuntimeError),
        ):
            change_plan(self.organization, big, 'monthly')
        entry = self.gateway_state.subscriptions[subscription.gateway_subscription_id]
        self.assertEqual(entry['value'], Decimal('100.00'))
        self.assertEqual(len(self.gateway_calls('cancel_payment')), 1)
        self.assertEqual(self.subscription.plan, hundred)
