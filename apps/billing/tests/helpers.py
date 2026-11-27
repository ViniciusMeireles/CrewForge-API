from apps.billing.factories.plans import PlanFactory
from apps.billing.models.subscription import Subscription

LIMITLESS = {
    'max_members': None,
    'max_teams': None,
    'storage_mb': None,
    'audit': True,
    'audit_retention_days': None,
}


def set_plan(organization, **entitlements):
    plan = PlanFactory(entitlements={**LIMITLESS, **entitlements})
    Subscription.objects.filter(organization=organization).update(plan=plan)
    if hasattr(organization, '_state'):
        organization._state.fields_cache.pop('subscription', None)
    return plan


def pro_plan():
    from apps.billing.models.plan import Plan

    return Plan.objects.get(code='pro')


def free_plan():
    from apps.billing.models.plan import Plan

    return Plan.objects.get(code='free')


class FakeGatewayMixin:
    """Resets the in-memory gateway before each test (BILLING_GATEWAY=fake)."""

    def setUp(self):
        from apps.billing.gateways import fake

        self.gateway_state = fake.reset()
        self.fake_gateway = fake.FakeGateway()
        super().setUp()

    def gateway_calls(self, operation: str) -> list[tuple]:
        return [args for name, args in self.gateway_state.calls if name == operation]


def make_paid(
    organization, *, plan=None, cycle='monthly', days_left=15, period_days=30, now=None
):
    from datetime import timedelta

    from django.utils import timezone

    from apps.billing.factories.payments import BillingProfileFactory
    from apps.billing.gateways import fake
    from apps.billing.models.subscription import Subscription
    from apps.billing.payments import reference

    now = now or timezone.now()
    plan = plan or pro_plan()
    from apps.billing.models.billing_profile import BillingProfile

    if not BillingProfile.objects.filter(organization=organization).exists():
        BillingProfileFactory(organization=organization)
    subscription = Subscription.objects.get(organization=organization)
    gateway = fake.FakeGateway()
    customer_id = gateway.upsert_customer(
        fake.CustomerData(
            name='Acme',
            tax_id='11222333000181',
            email='billing@acme.com',
            postal_code='01001000',
            street='Rua',
            number='1',
            complement='',
            district='Centro',
            external_reference=reference(subscription),
        )
    )
    price = plan.annual_price if cycle == 'annual' else plan.monthly_price
    end = now + timedelta(days=days_left)
    gateway_subscription_id = gateway.create_subscription(
        customer_id=customer_id,
        value=price,
        cycle=cycle,
        next_due_date=end.date(),
        description='test',
        external_reference=reference(subscription),
    )
    fake.STATE.calls.clear()
    subscription.plan = plan
    subscription.status = 'active'
    subscription.cycle = cycle
    subscription.trial_ends_at = None
    subscription.courtesy = ''
    subscription.current_period_start = end - timedelta(days=period_days)
    subscription.current_period_end = end
    subscription.gateway_customer_id = customer_id
    subscription.gateway_subscription_id = gateway_subscription_id
    subscription.save()
    return subscription
