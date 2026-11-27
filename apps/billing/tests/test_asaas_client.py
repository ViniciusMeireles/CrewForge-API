import json
import secrets
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.billing.gateways.asaas import AsaasGateway
from apps.billing.gateways.base import CustomerData, GatewayError, GatewayRejected

BASE = 'https://api-sandbox.asaas.com'


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode() if self.payload is not None else b''


def respond(payload, status=200):
    return FakeResponse(status, payload)


@override_settings(
    BILLING_PAYMENT_RETURN_URL='https://app.example.com/management/billing?payment=return'
)
class AsaasClientTestCase(SimpleTestCase):
    def setUp(self):
        self.api_key = secrets.token_urlsafe(16)
        self.gateway = AsaasGateway(base_url=BASE, api_key=self.api_key)
        patcher = mock.patch('http.client.HTTPSConnection')
        self.connection_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.connection = self.connection_class.return_value

    def answer(self, payload=None, status=200):
        self.connection.getresponse.return_value = respond(payload, status)

    def sent(self):
        method, path = self.connection.request.call_args.args
        kwargs = self.connection.request.call_args.kwargs
        body = json.loads(kwargs['body']) if kwargs.get('body') else None
        return method, path, kwargs['headers'], body

    def test_create_subscription_uses_undefined_billing_and_callback(self):
        self.answer({'id': 'sub_1'})
        result = self.gateway.create_subscription(
            customer_id='cus_1',
            value=Decimal('990.00'),
            cycle='annual',
            next_due_date=date(2026, 11, 26),
            description='Pro',
            external_reference='crewforge-subscription-7',
        )
        method, path, headers, body = self.sent()
        self.assertEqual(result, 'sub_1')
        self.assertEqual((method, path), ('POST', '/v3/subscriptions'))
        self.assertEqual(
            self.connection_class.call_args.args[0], 'api-sandbox.asaas.com'
        )
        self.assertEqual(headers['access_token'], self.api_key)
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
                self.answer(
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
        self.answer(
            {
                'id': 'pay_1',
                'status': 'PENDING',
                'deleted': True,
                'dueDate': '2026-11-26',
            }
        )
        self.assertEqual(self.gateway.get_payment('pay_1').status, 'canceled')

    def test_errors(self):
        self.answer({}, status=400)
        with self.assertRaises(GatewayRejected):
            self.gateway.delete_subscription('sub_1')
        self.answer(None, status=503)
        with self.assertRaises(GatewayError):
            self.gateway.delete_subscription('sub_1')
        self.connection.request.side_effect = TimeoutError()
        with self.assertRaises(GatewayError):
            self.gateway.delete_subscription('sub_1')

    def test_already_deleted_is_success(self):
        self.answer(None, status=404)
        self.gateway.delete_subscription('sub_gone')
        self.gateway.cancel_payment('pay_gone')

    def test_find_customer_by_reference(self):
        self.answer({'data': [{'id': 'cus_9'}]})
        self.assertEqual(
            self.gateway.find_customer('crewforge-subscription-7'), 'cus_9'
        )
        _, path, _, _ = self.sent()
        self.assertIn('externalReference=crewforge-subscription-7', path)
        self.answer({'data': []})
        self.assertEqual(self.gateway.find_customer('crewforge-subscription-8'), '')

    def test_missing_payment_returns_none(self):
        self.answer(None, status=404)
        self.assertIsNone(self.gateway.get_payment('pay_x'))

    def test_logs_carry_no_body(self):
        self.answer({'id': 'cus_1'})
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
            AsaasGateway(base_url='http://insecure', api_key=self.api_key)

    def test_parse_webhook(self):
        webhook = self.gateway.parse_webhook(
            {'id': 'evt_1', 'event': 'PAYMENT_RECEIVED', 'payment': {'id': 'pay_1'}}
        )
        self.assertEqual(
            (webhook.event_id, webhook.event_type, webhook.payment_id),
            ('evt_1', 'PAYMENT_RECEIVED', 'pay_1'),
        )
        self.assertIsNone(self.gateway.parse_webhook({'event': 'PAYMENT_RECEIVED'}))
