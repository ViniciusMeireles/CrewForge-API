import itertools
from dataclasses import replace
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from apps.billing.choices import GatewayChoices, InvoiceStatusChoices
from apps.billing.gateways.base import (
    CustomerData,
    GatewayError,
    GatewayPayment,
    GatewayWebhook,
)


class FakeState:
    def __init__(self) -> None:
        self.clear()

    def clear(self) -> None:
        self.ids = itertools.count(1)
        self.customers: dict[str, CustomerData] = {}
        self.subscriptions: dict[str, dict] = {}
        self.payments: dict[str, GatewayPayment] = {}
        self.calls: list[tuple[str, tuple]] = []
        self.fail_next = False

    def next_id(self, prefix: str) -> str:
        return f'{prefix}_{next(self.ids)}'


STATE = FakeState()


def reset() -> FakeState:
    STATE.clear()
    return STATE


def _payment_url(payment_id: str) -> str:
    base = (settings.FRONTEND_URL or 'http://localhost:4200').rstrip('/')
    return f'{base}/management/billing?payment=return&fake={payment_id}'


class FakeGateway:
    name = GatewayChoices.FAKE

    def _call(self, operation: str, *args) -> FakeState:
        state = STATE
        state.calls.append((operation, args))
        if state.fail_next:
            state.fail_next = False
            raise GatewayError(f'{operation} failed')
        return state

    def _new_payment(
        self, *, value: Decimal, due_date: date, subscription_id: str, reference: str
    ) -> GatewayPayment:
        state = STATE
        payment_id = state.next_id('pay')
        payment = GatewayPayment(
            id=payment_id,
            status=InvoiceStatusChoices.PENDING,
            value=value,
            due_date=due_date,
            issued_at=timezone.now(),
            paid_at=None,
            invoice_url=_payment_url(payment_id),
            subscription_id=subscription_id,
            external_reference=reference,
        )
        state.payments[payment_id] = payment
        return payment

    def find_customer(self, external_reference: str) -> str:
        state = self._call('find_customer', external_reference)
        for customer_id, data in state.customers.items():
            if data.external_reference == external_reference:
                return customer_id
        return ''

    def upsert_customer(self, data: CustomerData, customer_id: str = '') -> str:
        state = self._call('upsert_customer', customer_id)
        customer_id = customer_id or state.next_id('cus')
        state.customers[customer_id] = data
        return customer_id

    def create_subscription(
        self,
        *,
        customer_id,
        value,
        cycle,
        next_due_date,
        description,
        external_reference,
    ) -> str:
        state = self._call(
            'create_subscription', customer_id, value, cycle, next_due_date
        )
        subscription_id = state.next_id('sub')
        state.subscriptions[subscription_id] = {
            'customer': customer_id,
            'value': value,
            'cycle': cycle,
            'next_due_date': next_due_date,
            'reference': external_reference,
        }
        self._new_payment(
            value=value,
            due_date=next_due_date,
            subscription_id=subscription_id,
            reference=external_reference,
        )
        return subscription_id

    def update_subscription(
        self, subscription_id, *, value, cycle, next_due_date=None
    ) -> None:
        state = self._call(
            'update_subscription', subscription_id, value, cycle, next_due_date
        )
        entry = state.subscriptions[subscription_id]
        entry.update(value=value, cycle=cycle)
        if next_due_date is not None:
            entry['next_due_date'] = next_due_date
        for payment_id, payment in list(state.payments.items()):
            if (
                payment.subscription_id == subscription_id
                and payment.status == InvoiceStatusChoices.PENDING
            ):
                state.payments[payment_id] = replace(payment, value=value)

    def delete_subscription(self, subscription_id: str) -> None:
        state = self._call('delete_subscription', subscription_id)
        state.subscriptions.pop(subscription_id, None)
        for payment_id, payment in list(state.payments.items()):
            if payment.subscription_id == subscription_id and payment.status in (
                InvoiceStatusChoices.PENDING,
                InvoiceStatusChoices.OVERDUE,
            ):
                state.payments[payment_id] = replace(
                    payment, status=InvoiceStatusChoices.CANCELED
                )

    def list_subscription_payments(self, subscription_id: str) -> list[GatewayPayment]:
        state = self._call('list_subscription_payments', subscription_id)
        return [
            p for p in state.payments.values() if p.subscription_id == subscription_id
        ]

    def create_payment(
        self, *, customer_id, value, due_date, description, external_reference
    ) -> GatewayPayment:
        self._call('create_payment', customer_id, value, due_date)
        return self._new_payment(
            value=value,
            due_date=due_date,
            subscription_id='',
            reference=external_reference,
        )

    def cancel_payment(self, payment_id: str) -> None:
        state = self._call('cancel_payment', payment_id)
        payment = state.payments.get(payment_id)
        if payment is not None:
            state.payments[payment_id] = replace(
                payment, status=InvoiceStatusChoices.CANCELED
            )

    def get_payment(self, payment_id: str) -> GatewayPayment | None:
        state = self._call('get_payment', payment_id)
        return state.payments.get(payment_id)

    def parse_webhook(self, body: dict) -> GatewayWebhook | None:
        if not body.get('id') or not body.get('event'):
            return None
        payment = body.get('payment')
        return GatewayWebhook(
            event_id=str(body['id']),
            event_type=str(body['event']),
            payment_id=str(payment.get('id', '')) if isinstance(payment, dict) else '',
        )

    def set_status(self, payment_id: str, status: str) -> GatewayPayment:
        payment = STATE.payments[payment_id]
        paid_at = (
            timezone.now() if status == InvoiceStatusChoices.PAID else payment.paid_at
        )
        STATE.payments[payment_id] = replace(payment, status=status, paid_at=paid_at)
        return STATE.payments[payment_id]

    def add_recurring(self, subscription_id: str, due_date: date) -> GatewayPayment:
        entry = STATE.subscriptions[subscription_id]
        return self._new_payment(
            value=entry['value'],
            due_date=due_date,
            subscription_id=subscription_id,
            reference=entry['reference'],
        )
