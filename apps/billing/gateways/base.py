from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol


class GatewayError(Exception):
    """The gateway could not be reached or answered with a server error."""


class GatewayRejected(GatewayError):
    """The gateway refused the request (4xx)."""


@dataclass(frozen=True)
class CustomerData:
    name: str
    tax_id: str
    email: str
    postal_code: str
    street: str
    number: str
    complement: str
    district: str
    external_reference: str


@dataclass(frozen=True)
class GatewayPayment:
    id: str
    status: str
    value: Decimal
    due_date: date
    issued_at: datetime
    paid_at: datetime | None
    invoice_url: str
    subscription_id: str
    external_reference: str


@dataclass(frozen=True)
class GatewayWebhook:
    event_id: str
    event_type: str
    payment_id: str


class PaymentGateway(Protocol):
    name: str

    def upsert_customer(self, data: CustomerData, customer_id: str = '') -> str: ...

    def create_subscription(
        self,
        *,
        customer_id: str,
        value: Decimal,
        cycle: str,
        next_due_date: date,
        description: str,
        external_reference: str,
    ) -> str: ...

    def update_subscription(
        self,
        subscription_id: str,
        *,
        value: Decimal,
        cycle: str,
        next_due_date: date | None = None,
    ) -> None: ...

    def delete_subscription(self, subscription_id: str) -> None: ...

    def list_subscription_payments(
        self, subscription_id: str
    ) -> list[GatewayPayment]: ...

    def create_payment(
        self,
        *,
        customer_id: str,
        value: Decimal,
        due_date: date,
        description: str,
        external_reference: str,
    ) -> GatewayPayment: ...

    def cancel_payment(self, payment_id: str) -> None: ...

    def get_payment(self, payment_id: str) -> GatewayPayment | None: ...

    def parse_webhook(self, body: dict) -> GatewayWebhook | None: ...
