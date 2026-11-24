from django.db.models import Sum

from apps.accounts.models.files import StoredFile
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.billing.entitlements import (
    MAX_MEMBERS,
    MAX_TEAMS,
    plan_for,
    storage_bytes,
    value,
)
from apps.billing.models.subscription import Subscription
from apps.teams.models.team import Team


def active_members_count(organization: Organization) -> int:
    return Member.objects.filter(organization=organization, is_active=True).count()


def pending_invitations_count(organization: Organization) -> int:
    return Invitation.objects.filter(organization=organization).filter_pending().count()


def active_teams_count(organization: Organization) -> int:
    return Team.objects.filter(organization=organization, is_active=True).count()


def used_storage_bytes(organization: Organization) -> int:
    total = StoredFile.objects.filter(
        organization=organization, is_active=True
    ).aggregate(total=Sum('size'))['total']
    return total or 0


def usage(organization: Organization) -> dict[str, dict[str, int | None]]:
    plan = plan_for(organization)
    return {
        'members': {
            'current': active_members_count(organization),
            'max': value(plan, MAX_MEMBERS),
        },
        'teams': {
            'current': active_teams_count(organization),
            'max': value(plan, MAX_TEAMS),
        },
        'storage': {
            'current': used_storage_bytes(organization),
            'max': storage_bytes(plan),
        },
    }


def session_subscription(member: Member | None) -> Subscription | None:
    if member is None or not member.has_billing_access:
        return None
    try:
        return member.organization.subscription
    except Subscription.DoesNotExist:
        return None
