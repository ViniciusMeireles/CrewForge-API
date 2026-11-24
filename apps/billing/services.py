import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.models.organization import Organization
from apps.audit.choices import AuditActionChoices
from apps.audit.services import record_audit_event
from apps.billing import selectors
from apps.billing.choices import SubscriptionStatusChoices
from apps.billing.entitlements import MAX_MEMBERS, MAX_TEAMS, storage_bytes, value
from apps.billing.exceptions import STORAGE_BYTES, PlanLimitReached
from apps.billing.models.plan import Plan
from apps.billing.models.subscription import Subscription

logger = logging.getLogger(__name__)

User = get_user_model()


@transaction.atomic
def start_subscription(
    *, organization: Organization, owner, request=None, actor_member=None
):
    User.objects.select_for_update().filter(pk=owner.pk).first()
    already_trialing = (
        Subscription.objects.filter(
            status=SubscriptionStatusChoices.TRIALING,
            organization__members__user=owner,
            organization__members__role=MemberRoleChoices.OWNER,
            organization__members__is_active=True,
        )
        .exclude(organization=organization)
        .exists()
    )
    if already_trialing:
        return Subscription.objects.create(
            organization=organization,
            plan=Plan.objects.free(),
            status=SubscriptionStatusChoices.ACTIVE,
        )
    plan = Plan.objects.default()
    trial_ends_at = timezone.now() + timedelta(days=plan.trial_days)
    subscription = Subscription.objects.create(
        organization=organization,
        plan=plan,
        status=SubscriptionStatusChoices.TRIALING,
        trial_ends_at=trial_ends_at,
    )
    record_audit_event(
        AuditActionChoices.BILLING_SUBSCRIPTION_TRIAL_STARTED,
        request=request,
        organization_id=organization.pk,
        target=organization,
        actor_member=actor_member,
        metadata={
            'plan': plan.code,
            'trial_ends_at': trial_ends_at.isoformat(),
        },
    )
    return subscription


def _locked_plan(organization: Organization) -> Plan:
    subscription = (
        Subscription.objects.select_for_update(of=('self',))
        .select_related('plan')
        .filter(organization=organization)
        .first()
    )
    if subscription is None:
        logger.error(
            'billing.subscription_missing', extra={'organization_id': organization.pk}
        )
        return Plan.objects.free()
    return subscription.plan


def _limit_and_usage(
    organization: Organization, plan: Plan, key: str, count_pending: bool
) -> tuple[int | None, int]:
    if key == MAX_MEMBERS:
        current = selectors.active_members_count(organization)
        if count_pending:
            current += selectors.pending_invitations_count(organization)
        return value(plan, MAX_MEMBERS), current
    if key == MAX_TEAMS:
        return value(plan, MAX_TEAMS), selectors.active_teams_count(organization)
    if key == STORAGE_BYTES:
        return storage_bytes(plan), selectors.used_storage_bytes(organization)
    raise ValueError(key)


def ensure_within_limit(
    *,
    organization: Organization,
    key: str,
    adding: int = 1,
    count_pending: bool = False,
) -> None:
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError('ensure_within_limit needs an open transaction.')
    if adding <= 0:
        return
    plan = _locked_plan(organization)
    maximum, current = _limit_and_usage(organization, plan, key, count_pending)
    if maximum is None or current + adding <= maximum:
        return
    logger.info(
        'billing.limit_reached',
        extra={
            'organization_id': organization.pk,
            'limit': key,
            'current': current,
            'max': maximum,
        },
    )
    raise PlanLimitReached(key, current, maximum)
