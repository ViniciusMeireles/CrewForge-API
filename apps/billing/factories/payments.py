from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.billing.choices import (
    BillingCycleChoices,
    BrazilStateChoices,
    GatewayChoices,
    InvoiceKindChoices,
    InvoiceStatusChoices,
)
from apps.billing.models.billing_profile import BillingProfile
from apps.billing.models.gateway_event import GatewayEvent
from apps.billing.models.invoice import Invoice
from apps.generics.factories.mixins import ModelFactoryMixin

VALID_CNPJ = '11222333000181'
VALID_CPF = '52998224725'


class BillingProfileFactory(ModelFactoryMixin):
    organization = factory.SubFactory(
        'apps.accounts.factories.organizations.OrganizationFactory'
    )
    legal_name = 'Acme Tecnologia Ltda'
    tax_id = VALID_CNPJ
    email = factory.Sequence(lambda n: f'billing{n}@acme.com')
    postal_code = '01001000'
    street = 'Rua das Flores'
    number = '120'
    complement = 'Sala 4'
    district = 'Centro'
    city = 'São Paulo'
    state = BrazilStateChoices.SP

    class Meta:
        model = BillingProfile


class InvoiceFactory(ModelFactoryMixin):
    subscription = factory.SubFactory(
        'apps.billing.factories.plans.SubscriptionFactory'
    )
    gateway = GatewayChoices.FAKE
    gateway_id = factory.Sequence(lambda n: f'pay_f{n}')
    kind = InvoiceKindChoices.RECURRING
    plan = factory.SelfAttribute('subscription.plan')
    cycle = BillingCycleChoices.MONTHLY
    amount = Decimal('99.00')
    issued_at = factory.LazyFunction(timezone.now)
    due_date = factory.LazyFunction(lambda: timezone.localdate() + timedelta(days=3))
    status = InvoiceStatusChoices.PENDING
    payment_url = 'https://sandbox.asaas.com/i/abc'

    class Meta:
        model = Invoice


class GatewayEventFactory(DjangoModelFactory):
    gateway = GatewayChoices.ASAAS
    event_id = factory.Sequence(lambda n: f'evt_{n}')
    event_type = 'PAYMENT_RECEIVED'
    payload = factory.LazyFunction(dict)

    class Meta:
        model = GatewayEvent
