import json
import logging
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.billing.choices import (
    BillingCycleChoices,
    GatewayChoices,
    InvoiceStatusChoices,
)
from apps.billing.gateways.base import (
    CustomerData,
    GatewayError,
    GatewayPayment,
    GatewayRejected,
    GatewayWebhook,
)

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10
BILLING_TYPE = 'UNDEFINED'
CYCLES: dict[str, str] = {
    BillingCycleChoices.MONTHLY: 'MONTHLY',
    BillingCycleChoices.ANNUAL: 'YEARLY',
}
STATUSES = {
    'PENDING': InvoiceStatusChoices.PENDING,
    'AWAITING_RISK_ANALYSIS': InvoiceStatusChoices.PENDING,
    'RECEIVED': InvoiceStatusChoices.PAID,
    'CONFIRMED': InvoiceStatusChoices.PAID,
    'RECEIVED_IN_CASH': InvoiceStatusChoices.PAID,
    'OVERDUE': InvoiceStatusChoices.OVERDUE,
    'REFUNDED': InvoiceStatusChoices.REFUNDED,
    'REFUND_REQUESTED': InvoiceStatusChoices.REFUNDED,
    'REFUND_IN_PROGRESS': InvoiceStatusChoices.REFUNDED,
    'CHARGEBACK_REQUESTED': InvoiceStatusChoices.REFUNDED,
    'CHARGEBACK_DISPUTE': InvoiceStatusChoices.REFUNDED,
    'AWAITING_CHARGEBACK_REVERSAL': InvoiceStatusChoices.REFUNDED,
}


def _status(payment: dict) -> str:
    if payment.get('deleted'):
        return InvoiceStatusChoices.CANCELED
    return STATUSES.get(str(payment.get('status')), InvoiceStatusChoices.PENDING)


def _moment(value) -> datetime | None:
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed is None:
        day = parse_date(str(value))
        if day is None:
            return None
        parsed = datetime(day.year, day.month, day.day)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def _payment(data: dict) -> GatewayPayment:
    status = _status(data)
    paid_at = None
    if status == InvoiceStatusChoices.PAID:
        paid_at = (
            _moment(
                data.get('confirmedDate')
                or data.get('paymentDate')
                or data.get('clientPaymentDate')
            )
            or timezone.now()
        )
    return GatewayPayment(
        id=str(data['id']),
        status=status,
        value=Decimal(str(data.get('value', '0'))),
        due_date=parse_date(str(data.get('dueDate'))) or timezone.localdate(),
        issued_at=_moment(data.get('dateCreated')) or timezone.now(),
        paid_at=paid_at,
        invoice_url=str(data.get('invoiceUrl') or ''),
        subscription_id=str(data.get('subscription') or ''),
        external_reference=str(data.get('externalReference') or ''),
    )


class AsaasGateway:
    name = GatewayChoices.ASAAS

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or settings.ASAAS_API_URL).rstrip('/')
        if not self.base_url.startswith('https://'):
            raise GatewayError('The Asaas API URL must use https.')
        self.api_key = api_key if api_key is not None else settings.ASAAS_API_KEY

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(  # noqa: S310
            f'{self.base_url}{path}',
            data=data,
            method=method,
            headers={
                'access_token': self.api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'crewforge-billing',
            },
        )
        started = time.monotonic()
        status = 0
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
                status = response.status
                raw = response.read()
        except urllib.error.HTTPError as error:
            status = error.code
            if HTTPStatus.BAD_REQUEST <= error.code < HTTPStatus.INTERNAL_SERVER_ERROR:
                if error.code == HTTPStatus.NOT_FOUND and method in ('GET', 'DELETE'):
                    return {}
                raise GatewayRejected(
                    f'{method} {path.split("?", maxsplit=1)[0]} {error.code}'
                ) from None
            raise GatewayError(
                f'{method} {path.split("?", maxsplit=1)[0]} {error.code}'
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise GatewayError(
                f'{method} {path.split("?", maxsplit=1)[0]} unreachable'
            ) from error
        finally:
            logger.info(
                'billing.gateway_call',
                extra={
                    'gateway': self.name,
                    'operation': f'{method} {path.split("?", maxsplit=1)[0]}',
                    'status': status,
                    'duration_ms': round((time.monotonic() - started) * 1000),
                },
            )
        return json.loads(raw) if raw else {}

    def _callback(self) -> dict:
        url = settings.BILLING_PAYMENT_RETURN_URL
        return {'callback': {'successUrl': url, 'autoRedirect': True}} if url else {}

    def find_customer(self, external_reference: str) -> str:
        data = self._request(
            'GET', f'/v3/customers?externalReference={quote(external_reference)}'
        )
        found = data.get('data') or []
        return str(found[0]['id']) if found else ''

    def upsert_customer(self, data: CustomerData, customer_id: str = '') -> str:
        body = {
            'name': data.name,
            'cpfCnpj': data.tax_id,
            'email': data.email,
            'postalCode': data.postal_code,
            'address': data.street,
            'addressNumber': data.number,
            'complement': data.complement,
            'province': data.district,
            'externalReference': data.external_reference,
            'notificationDisabled': False,
        }
        if customer_id:
            self._request('PUT', f'/v3/customers/{quote(customer_id)}', body)
            return customer_id
        return str(self._request('POST', '/v3/customers', body)['id'])

    def create_subscription(
        self,
        *,
        customer_id: str,
        value: Decimal,
        cycle: str,
        next_due_date: date,
        description: str,
        external_reference: str,
    ) -> str:
        body = {
            'customer': customer_id,
            'billingType': BILLING_TYPE,
            'value': str(value),
            'nextDueDate': next_due_date.isoformat(),
            'cycle': CYCLES[cycle],
            'description': description,
            'externalReference': external_reference,
            **self._callback(),
        }
        return str(self._request('POST', '/v3/subscriptions', body)['id'])

    def update_subscription(
        self,
        subscription_id: str,
        *,
        value: Decimal,
        cycle: str,
        next_due_date: date | None = None,
    ) -> None:
        body = {
            'value': str(value),
            'cycle': CYCLES[cycle],
            'updatePendingPayments': True,
        }
        if next_due_date is not None:
            body['nextDueDate'] = next_due_date.isoformat()
        self._request('PUT', f'/v3/subscriptions/{quote(subscription_id)}', body)

    def delete_subscription(self, subscription_id: str) -> None:
        self._request('DELETE', f'/v3/subscriptions/{quote(subscription_id)}')

    def list_subscription_payments(self, subscription_id: str) -> list[GatewayPayment]:
        data = self._request(
            'GET', f'/v3/subscriptions/{quote(subscription_id)}/payments?limit=100'
        )
        return [_payment(item) for item in data.get('data', [])]

    def create_payment(
        self,
        *,
        customer_id: str,
        value: Decimal,
        due_date: date,
        description: str,
        external_reference: str,
    ) -> GatewayPayment:
        body = {
            'customer': customer_id,
            'billingType': BILLING_TYPE,
            'value': str(value),
            'dueDate': due_date.isoformat(),
            'description': description,
            'externalReference': external_reference,
            **self._callback(),
        }
        return _payment(self._request('POST', '/v3/payments', body))

    def cancel_payment(self, payment_id: str) -> None:
        self._request('DELETE', f'/v3/payments/{quote(payment_id)}')

    def get_payment(self, payment_id: str) -> GatewayPayment | None:
        data = self._request('GET', f'/v3/payments/{quote(payment_id)}')
        return _payment(data) if data.get('id') else None

    def parse_webhook(self, body: dict) -> GatewayWebhook | None:
        event_id = body.get('id')
        event_type = body.get('event')
        if not event_id or not event_type:
            return None
        payment = body.get('payment')
        payment_id = payment.get('id', '') if isinstance(payment, dict) else ''
        return GatewayWebhook(
            event_id=str(event_id),
            event_type=str(event_type),
            payment_id=str(payment_id),
        )
