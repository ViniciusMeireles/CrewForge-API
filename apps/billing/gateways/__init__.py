from django.conf import settings
from django.utils.module_loading import import_string

from apps.billing.gateways.base import PaymentGateway

GATEWAYS = {
    'asaas': 'apps.billing.gateways.asaas.AsaasGateway',
    'fake': 'apps.billing.gateways.fake.FakeGateway',
}


def get_gateway() -> PaymentGateway:
    return import_string(GATEWAYS[settings.BILLING_GATEWAY])()
