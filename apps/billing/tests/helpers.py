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
