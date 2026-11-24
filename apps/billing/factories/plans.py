from decimal import Decimal

import factory

from apps.billing.choices import SubscriptionStatusChoices
from apps.billing.models.plan import Plan
from apps.billing.models.subscription import Subscription
from apps.generics.factories.mixins import ModelFactoryMixin

UNLIMITED_PLAN_CODE = 'test-unlimited'


def unlimited_plan() -> Plan:
    plan, _ = Plan.objects.get_or_create(
        code=UNLIMITED_PLAN_CODE,
        defaults={
            'name': 'Unlimited',
            'monthly_price': Decimal('1.00'),
            'annual_price': Decimal('10.00'),
            'is_public': False,
            'entitlements': {
                'max_members': None,
                'max_teams': None,
                'storage_mb': None,
                'audit': True,
                'audit_retention_days': None,
            },
        },
    )
    return plan


class PlanFactory(ModelFactoryMixin):
    code = factory.Sequence(lambda n: f'plan-{n}')
    name = factory.Sequence(lambda n: f'Plan {n}')
    monthly_price = Decimal('49.00')
    annual_price = Decimal('490.00')
    entitlements = factory.LazyFunction(
        lambda: {
            'max_members': 10,
            'max_teams': 5,
            'storage_mb': 1024,
            'audit': True,
            'audit_retention_days': 90,
        }
    )

    class Meta:
        model = Plan


class SubscriptionFactory(ModelFactoryMixin):
    organization = factory.SubFactory(
        'apps.accounts.factories.organizations.OrganizationFactory',
        subscription=False,
    )
    plan = factory.LazyFunction(unlimited_plan)
    status = SubscriptionStatusChoices.ACTIVE

    class Meta:
        model = Subscription
