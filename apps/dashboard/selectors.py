from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from django.db.models import Count, Q
from django.db.models.functions import Lower

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.dashboard.consts import (
    DASHBOARD_EXPIRING_SOON_DAYS,
    DASHBOARD_LIST_LIMIT,
)
from apps.teams.models.team import Team
from apps.teams.models.team_member import TeamMember

if TYPE_CHECKING:
    from django.contrib.auth import get_user_model

    User = get_user_model()


def members_section(*, organization_id: int) -> dict:
    members = Member.objects.filter(organization_id=organization_id, is_active=True)
    counts = members.aggregate(
        **{role: Count('id', filter=Q(role=role)) for role in MemberRoleChoices.values},
    )
    by_role = [
        {
            'role': role,
            'role_label': MemberRoleChoices(role).label,
            'count': counts[role],
        }
        for role in MemberRoleChoices.values
    ]
    recent = list(
        members.select_related('user').order_by('-created_at', '-id')[
            :DASHBOARD_LIST_LIMIT
        ],
    )
    return {'total': sum(counts.values()), 'by_role': by_role, 'recent': recent}


def teams_section(*, member: Member, organization_id: int) -> dict:
    total = Team.objects.filter(
        organization_id=organization_id,
        is_active=True,
    ).count()
    mine = TeamMember.objects.filter(
        member=member,
        is_active=True,
        team__is_active=True,
        team__organization_id=organization_id,
    )
    mine_count = mine.count()
    mine_list = list(
        mine.annotate(
            member_count=Count(
                'team__members',
                filter=Q(
                    team__members__is_active=True,
                    team__members__member__is_active=True,
                ),
            ),
        )
        .select_related('team')
        .order_by(Lower('team__name'), 'team_id')[:DASHBOARD_LIST_LIMIT],
    )
    return {'total': total, 'mine_count': mine_count, 'mine': mine_list}


def invitations_section(
    *,
    member: Member,
    organization_id: int,
    now: datetime,
) -> dict:
    pending = (
        Invitation.objects.filter(organization_id=organization_id)
        .filter_acceptable()
        .filter_visible_to(member)
    )
    expiring_soon = list(
        pending.filter(
            expired_at__isnull=False,
            expired_at__lte=now + timedelta(days=DASHBOARD_EXPIRING_SOON_DAYS),
        ).order_by('expired_at', 'id')[:DASHBOARD_LIST_LIMIT],
    )
    return {'pending': pending.count(), 'expiring_soon': expiring_soon}


def received_invitations_section(*, user: 'User') -> dict:
    pending = Invitation.objects.filter_received_by_user(user).filter_acceptable()
    return {'pending': pending.count()}


def build_overview(*, member: Member, user: 'User', now: datetime) -> dict:
    organization_id = member.organization_id
    return {
        'generated_at': now,
        'member': member,
        'members': members_section(organization_id=organization_id)
        if member.has_members_access
        else None,
        'teams': teams_section(member=member, organization_id=organization_id)
        if member.has_teams_access
        else None,
        'invitations': invitations_section(
            member=member,
            organization_id=organization_id,
            now=now,
        )
        if member.has_invitations_access
        else None,
        'received_invitations': received_invitations_section(user=user),
    }
