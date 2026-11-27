from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.models.audit_event import AuditEvent
from apps.billing.factories.payments import BillingProfileFactory
from apps.billing.models.gateway_event import GatewayEvent
from apps.billing.models.invoice import Invoice
from apps.billing.models.subscription import Subscription
from apps.billing.payments import change_plan, sync_invoice
from apps.billing.tests.helpers import FakeGatewayMixin, make_paid, pro_plan

TOKEN = 'test-webhook-token'


def event(event_id, payment_id, event_type='PAYMENT_RECEIVED'):
    return {'id': event_id, 'event': event_type, 'payment': {'id': payment_id}}


@override_settings(ASAAS_WEBHOOK_TOKEN=TOKEN)
class WebhookTestCase(FakeGatewayMixin, APITestCase):
    url = reverse('billing:webhook-asaas')

    def setUp(self):
        super().setUp()
        self.organization = OrganizationFactory()
        BillingProfileFactory(organization=self.organization)
        self.subscription, self.payment_url = change_plan(
            self.organization, pro_plan(), 'monthly'
        )
        self.invoice = Invoice.objects.get()

    def send(self, body, token=TOKEN):
        headers = {'HTTP_ASAAS_ACCESS_TOKEN': token} if token is not None else {}
        return self.client.post(self.url, body, format='json', **headers)

    def test_missing_token_401(self):
        response = self.send(event('evt_1', self.invoice.gateway_id), token=None)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(GatewayEvent.objects.exists())

    def test_wrong_token_401(self):
        with self.assertLogs('apps.billing.authentication', level='WARNING'):
            response = self.send(event('evt_1', self.invoice.gateway_id), token='nope')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(GatewayEvent.objects.exists())

    @override_settings(ASAAS_WEBHOOK_TOKEN='')
    def test_unset_token_refuses_everything(self):
        response = self.send(event('evt_1', self.invoice.gateway_id), token='')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_paid_event_activates_the_pending_change(self):
        self.fake_gateway.set_status(self.invoice.gateway_id, 'paid')
        with self.captureOnCommitCallbacks(execute=True):
            response = self.send(event('evt_1', self.invoice.gateway_id))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        subscription = Subscription.objects.get(pk=self.subscription.pk)
        self.assertEqual(
            (subscription.status, subscription.cycle), ('active', 'monthly')
        )
        self.assertEqual(subscription.plan, pro_plan())
        self.assertIsNone(subscription.pending_plan)
        self.assertIsNotNone(subscription.current_period_end)
        self.assertIsNone(subscription.trial_ends_at)
        self.assertEqual(Invoice.objects.get().status, 'paid')
        self.assertIsNotNone(GatewayEvent.objects.get().processed_at)
        activated = AuditEvent.objects.get(
            action=AuditActionChoices.BILLING_SUBSCRIPTION_ACTIVATED
        )
        self.assertEqual(activated.actor_type, AuditActorTypeChoices.SYSTEM)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditActionChoices.BILLING_INVOICE_PAID
            ).exists()
        )

    def test_duplicate_event_no_effect(self):
        self.fake_gateway.set_status(self.invoice.gateway_id, 'paid')
        with self.captureOnCommitCallbacks(execute=True):
            self.send(event('evt_1', self.invoice.gateway_id))
        with self.captureOnCommitCallbacks(execute=True):
            response = self.send(event('evt_1', self.invoice.gateway_id))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(GatewayEvent.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditActionChoices.BILLING_SUBSCRIPTION_ACTIVATED
            ).count(),
            1,
        )

    def test_reordered_events_final_state(self):
        self.fake_gateway.set_status(self.invoice.gateway_id, 'paid')
        with self.captureOnCommitCallbacks(execute=True):
            self.send(event('evt_2', self.invoice.gateway_id, 'PAYMENT_RECEIVED'))
        with self.captureOnCommitCallbacks(execute=True):
            self.send(event('evt_1', self.invoice.gateway_id, 'PAYMENT_CREATED'))
        self.assertEqual(Invoice.objects.get().status, 'paid')
        self.assertEqual(
            Subscription.objects.get(pk=self.subscription.pk).status, 'active'
        )

    def test_unknown_event_type_is_stored_and_processed(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.send({'id': 'evt_9', 'event': 'SUBSCRIPTION_UPDATED'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsNotNone(GatewayEvent.objects.get().processed_at)

    def test_unknown_payment_is_stored_with_an_error(self):
        payment = self.fake_gateway.create_payment(
            customer_id='cus_x',
            value=Decimal('10.00'),
            due_date=self.invoice.due_date,
            description='x',
            external_reference='other',
        )
        with (
            self.assertLogs('apps.billing.tasks', level='WARNING'),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.send(event('evt_3', payment.id))
        stored = GatewayEvent.objects.get()
        self.assertEqual(stored.error, 'unknown payment')

    def test_unparseable_body_is_accepted(self):
        response = self.send({'something': 'else'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(GatewayEvent.objects.exists())

    def test_gateway_failure_keeps_the_event_for_retry(self):
        with mock.patch('apps.billing.tasks.process_gateway_event.delay'):
            self.send(event('evt_4', self.invoice.gateway_id))
        stored = GatewayEvent.objects.get()
        from apps.billing.gateways.base import GatewayError
        from apps.billing.tasks import process_gateway_event

        self.gateway_state.fail_next = True
        with (
            self.assertRaises(GatewayError),
            self.assertLogs('apps.billing', level='WARNING'),
        ):
            process_gateway_event.apply(args=[stored.pk], throw=True, retries=5)
        stored.refresh_from_db()
        self.assertIsNone(stored.processed_at)
        self.assertTrue(stored.error)


class SyncInvoiceTestCase(FakeGatewayMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.organization = OrganizationFactory()
        self.subscription = make_paid(self.organization)

    def recurring(self):
        return self.fake_gateway.add_recurring(
            self.subscription.gateway_subscription_id,
            self.subscription.current_period_end.date(),
        )

    def test_recurring_paid_records_the_payment(self):
        payment = self.recurring()
        self.fake_gateway.set_status(payment.id, 'paid')
        invoice = sync_invoice(payment.id)
        self.assertEqual((invoice.status, invoice.kind), ('paid', 'recurring'))
        self.assertIsNotNone(invoice.paid_at)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditActionChoices.BILLING_INVOICE_PAID
            ).exists()
        )

    def test_refunded_keeps_the_plan(self):
        payment = self.recurring()
        self.fake_gateway.set_status(payment.id, 'paid')
        sync_invoice(payment.id)
        self.fake_gateway.set_status(payment.id, 'refunded')
        invoice = sync_invoice(payment.id)
        self.assertEqual(invoice.status, 'refunded')
        self.assertEqual(
            Subscription.objects.get(pk=self.subscription.pk).plan, pro_plan()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditActionChoices.BILLING_INVOICE_REFUNDED
            ).exists()
        )

    def test_overdue_and_deleted_change_status_only(self):
        payment = self.recurring()
        for status in ('overdue', 'canceled'):
            with self.subTest(status=status):
                self.fake_gateway.set_status(payment.id, status)
                self.assertEqual(sync_invoice(payment.id).status, status)
        self.assertEqual(
            Subscription.objects.get(pk=self.subscription.pk).status, 'active'
        )

    def test_missing_payment(self):
        self.assertIsNone(sync_invoice('pay_missing'))
