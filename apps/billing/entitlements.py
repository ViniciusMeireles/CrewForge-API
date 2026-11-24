import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from apps.accounts.models.member import Member
    from apps.accounts.models.organization import Organization
    from apps.billing.models.plan import Plan

logger = logging.getLogger(__name__)

BYTES_PER_MB = 1024 * 1024
FALLBACK_PLAN_ATTRIBUTE = '_billing_fallback_plan'


class Kind(StrEnum):
    LIMIT = 'limit'
    FLAG = 'flag'


@dataclass(frozen=True)
class Entitlement:
    key: str
    kind: Kind
    default: Any


MAX_MEMBERS = 'max_members'
MAX_TEAMS = 'max_teams'
STORAGE_MB = 'storage_mb'
AUDIT = 'audit'
AUDIT_RETENTION_DAYS = 'audit_retention_days'

CATALOG: dict[str, Entitlement] = {
    entry.key: entry
    for entry in (
        Entitlement(MAX_MEMBERS, Kind.LIMIT, 0),
        Entitlement(MAX_TEAMS, Kind.LIMIT, 0),
        Entitlement(STORAGE_MB, Kind.LIMIT, 0),
        Entitlement(AUDIT, Kind.FLAG, False),
        Entitlement(AUDIT_RETENTION_DAYS, Kind.LIMIT, None),
    )
}


def _valid_value(entry: Entitlement, value: Any) -> bool:
    if entry.kind == Kind.FLAG:
        return isinstance(value, bool)
    if value is None:
        return True
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_entitlements(values: Any) -> None:
    if not isinstance(values, dict):
        raise ValidationError({'entitlements': _('Entitlements must be an object.')})
    errors = []
    for key, value in values.items():
        entry = CATALOG.get(key)
        if entry is None:
            message = _('Unknown entitlement.')
        elif not _valid_value(entry, value):
            message = (
                _('Enter true or false.')
                if entry.kind == Kind.FLAG
                else _('Enter a non-negative integer or null.')
            )
        else:
            continue
        errors.append(f'{key}: {message}')
    if errors:
        raise ValidationError({'entitlements': errors})


def value(plan: Plan, key: str) -> Any:
    entry = CATALOG[key]
    values = plan.entitlements or {}
    if key not in values or not _valid_value(entry, values[key]):
        return entry.default
    return values[key]


def storage_bytes(plan: Plan) -> int | None:
    megabytes = value(plan, STORAGE_MB)
    return None if megabytes is None else megabytes * BYTES_PER_MB


def plan_for(organization: Organization) -> Plan:
    from apps.billing.models.plan import Plan
    from apps.billing.models.subscription import Subscription

    try:
        return organization.subscription.plan
    except Subscription.DoesNotExist:
        pass
    fallback = getattr(organization, FALLBACK_PLAN_ATTRIBUTE, None)
    if fallback is None:
        logger.error(
            'billing.subscription_missing',
            extra={'organization_id': organization.pk},
        )
        fallback = Plan.objects.free()
        setattr(organization, FALLBACK_PLAN_ATTRIBUTE, fallback)
    return fallback


def has_feature(member: Member, key: str) -> bool:
    return bool(value(plan_for(member.organization), key))
