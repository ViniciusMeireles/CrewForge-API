from datetime import timedelta
from decimal import Decimal

PRO_CODE = 'pro'
FREE_CODE = 'free'
BATCH_SIZE = 1000

SEED_PLANS = (
    {
        'code': FREE_CODE,
        'name': 'Free',
        'monthly_price': Decimal('0.00'),
        'annual_price': Decimal('0.00'),
        'trial_days': 0,
        'is_public': True,
        'is_default': False,
        'is_free': True,
        'sort_order': 0,
        'entitlements': {
            'max_members': 3,
            'max_teams': 1,
            'storage_mb': 100,
            'audit': False,
            'audit_retention_days': None,
        },
    },
    {
        'code': PRO_CODE,
        'name': 'Pro',
        'monthly_price': Decimal('99.00'),
        'annual_price': Decimal('990.00'),
        'trial_days': 14,
        'is_public': True,
        'is_default': True,
        'is_free': False,
        'sort_order': 1,
        'entitlements': {
            'max_members': 25,
            'max_teams': 10,
            'storage_mb': 5120,
            'audit': True,
            'audit_retention_days': 365,
        },
    },
)


def seed_plans(plan_model) -> int:
    if plan_model.objects.exists():
        return 0
    for values in SEED_PLANS:
        plan_model.objects.create(**values)
    return len(SEED_PLANS)


def remove_seed_plans(plan_model) -> None:
    plan_model.objects.filter(
        code__in=[values['code'] for values in SEED_PLANS],
        subscriptions__isnull=True,
    ).delete()


def create_courtesy_subscriptions(organization_model, subscription_model, plan_model):
    plan = plan_model.objects.filter(is_default=True).first()
    if plan is None:
        return 0
    created = 0
    pending = organization_model.objects.filter(subscription__isnull=True).order_by(
        'pk'
    )
    while ids := list(pending.values_list('pk', flat=True)[:BATCH_SIZE]):
        subscription_model.objects.bulk_create(
            [
                subscription_model(
                    organization_id=organization_id,
                    plan=plan,
                    status='active',
                    courtesy='legacy',
                )
                for organization_id in ids
            ],
            ignore_conflicts=True,
        )
        created += len(ids)
    return created


def convert_legacy_courtesy_to_trial(subscription_model, plan_model, now) -> int:
    plan = plan_model.objects.filter(is_default=True).first()
    if plan is None:
        return 0
    return subscription_model.objects.filter(
        courtesy='legacy', status='active', cycle__isnull=True
    ).update(
        plan=plan,
        status='trialing',
        trial_ends_at=now + timedelta(days=plan.trial_days),
    )


def restore_legacy_courtesy(subscription_model) -> int:
    return subscription_model.objects.filter(
        courtesy='legacy', status='trialing', cycle__isnull=True
    ).update(status='active', trial_ends_at=None)
