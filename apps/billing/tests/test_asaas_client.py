import io
import json
import urllib.error
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.billing.gateways.asaas import AsaasGateway
from apps.billing.gateways.base import CustomerData, GatewayError, GatewayRejected

BASE = 'https://api-sandbox.asaas.com'


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def respond(payload):
    return FakeResponse(json.dumps(payload).encode())


@override_settings(
    BILLING_PAYMENT_RETURN_URL='https://app.example.com/management/billing?payment=return'
)
class AsaasClientTestCase(SimpleTestCase):
    def setUp(self):
        self.gateway = AsaasGateway(base_url=BASE, api_key='test-key')
        patcher = mock.patch('urllib.request.urlopen')
        self.urlopen = patcher.start()
        self.addCleanup(patcher.stop)

    def sent(self):
        request = self.urlopen.call_args.args[0]
        body = json.loads(request.data) if request.data else None
        return request, body

    def test_create_subscription_uses_undefined_billing_and_callback(self):
        self.urlopen.return_value = respond({'id': 'sub_1'})
        result = self.gateway.create_subscription(
            customer_id='cus_1',
            value=Decimal('990.00'),
            cycle='annual',
            next_due_date=date(2026, 11, 26),
            description='Pro',
            external_reference='crewforge-subscription-7',
        )
        request, body = self.sent()
        self.assertEqual(result, 'sub_1')
        self.assertEqual(request.full_url, f'{BASE}/v3/subscriptions')
        self.assertEqual(request.get_header('Access_token'), 'test-key')
        self.assertEqual(body['billingType'], 'UNDEFINED')
        self.assertEqual(body['cycle'], 'YEARLY')
        self.assertEqual(body['value'], '990.00')
        self.assertEqual(
            body['callback']['successUrl'],
            'https://app.example.com/management/billing?payment=return',
        )

    def test_payment_status_map(self):
        cases = {
            'PENDING': 'pending',
            'RECEIVED': 'paid',
            'CONFIRMED': 'paid',
            'OVERDUE': 'overdue',
            'REFUNDED': 'refunded',
            'CHARGEBACK_REQUESTED': 'refunded',
        }
        for asaas_status, expected in cases.items():
            with self.subTest(status=asaas_status):
                self.urlopen.return_value = respond(
                    {
                        'id': 'pay_1',
                        'status': asaas_status,
                        'value': 99,
                        'dueDate': '2026-11-26',
                        'dateCreated': '2026-11-20',
                        'paymentDate': '2026-11-26',
                        'invoiceUrl': 'https://sandbox.asaas.com/i/1',
                        'subscription': 'sub_1',
                    }
                )
                payment = self.gateway.get_payment('pay_1')
                self.assertEqual(payment.status, expected)
                self.assertEqual(payment.value, Decimal('99'))
                self.assertEqual(payment.paid_at is not None, expected == 'paid')

    def test_deleted_payment_is_canceled(self):
        self.urlopen.return_value = respond(
            {
                'id': 'pay_1',
                'status': 'PENDING',
                'deleted': True,
                'dueDate': '2026-11-26',
            }
        )
        self.assertEqual(self.gateway.get_payment('pay_1').status, 'canceled')

    def test_errors(self):
        self.urlopen.side_effect = urllib.error.HTTPError(
            BASE, 400, 'bad', {}, io.BytesIO(b'{}')
        )
        with self.assertRaises(GatewayRejected):
            self.gateway.delete_subscription('sub_1')
        self.urlopen.side_effect = urllib.error.HTTPError(
            BASE, 503, 'down', {}, io.BytesIO(b'')
        )
        with self.assertRaises(GatewayError):
            self.gateway.delete_subscription('sub_1')
        self.urlopen.side_effect = TimeoutError()
        with self.assertRaises(GatewayError):
            self.gateway.delete_subscription('sub_1')

    def test_missing_payment_returns_none(self):
        self.urlopen.side_effect = urllib.error.HTTPError(
            BASE, 404, 'nf', {}, io.BytesIO(b'')
        )
        self.assertIsNone(self.gateway.get_payment('pay_x'))

    def test_logs_carry_no_body(self):
        self.urlopen.return_value = respond({'id': 'cus_1'})
        with self.assertLogs('apps.billing.gateways.asaas', level='INFO') as logs:
            self.gateway.upsert_customer(
                CustomerData(
                    name='x',
                    tax_id='11222333000181',
                    email='billing@acme.com',
                    postal_code='01001000',
                    street='Rua',
                    number='1',
                    complement='',
                    district='Centro',
                    external_reference='ref',
                )
            )
        self.assertNotIn('11222333000181', ''.join(logs.output))
        self.assertNotIn('billing@acme.com', ''.join(logs.output))

    def test_http_base_url_is_refused(self):
        with self.assertRaises(GatewayError):
            AsaasGateway(base_url='http://insecure', api_key='k')

    def test_parse_webhook(self):
        webhook = self.gateway.parse_webhook(
            {'id': 'evt_1', 'event': 'PAYMENT_RECEIVED', 'payment': {'id': 'pay_1'}}
        )
        self.assertEqual(
            (webhook.event_id, webhook.event_type, webhook.payment_id),
            ('evt_1', 'PAYMENT_RECEIVED', 'pay_1'),
        )
        self.assertIsNone(self.gateway.parse_webhook({'event': 'PAYMENT_RECEIVED'}))
