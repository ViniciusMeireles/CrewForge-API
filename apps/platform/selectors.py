from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db.models import (
    Count,
    IntegerField,
    Max,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce

from apps.accounts.choices import OrganizationStatusChoices
from apps.accounts.models.files import StoredFile
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.platform.consts import (
    PLATFORM_ACTIVE_ORGANIZATION_DAYS,
    PLATFORM_NEW_RECORDS_DAYS,
)
from apps.teams.models.team import Team

User = get_user_model()


def _subquery_aggregate(queryset: QuerySet, expression, field: str = 'organization'):
    rows = queryset.filter(**{field: OuterRef('pk')}).order_by().values(field)
    return Coalesce(
        Subquery(rows.annotate(value=expression).values('value')[:1]),
        Value(0),
        output_field=IntegerField(),
    )


def _active_members():
    return Member.objects.filter(is_active=True, user__is_active=True)


def organizations_queryset() -> QuerySet[Organization]:
    return (
        Organization.objects.with_owner()
        .select_related('profile', 'suspended_by')
        .annotate(
            active_members_count=_subquery_aggregate(_active_members(), Count('id')),
            last_access_at=Subquery(
                _active_members()
                .filter(organization=OuterRef('pk'))
                .order_by()
                .values('organization')
                .annotate(value=Max('last_login_at'))
                .values('value')[:1]
            ),
        )
        .order_by('-created_at', '-id')
    )


def organization_detail_queryset() -> QuerySet[Organization]:
    return organizations_queryset().annotate(
        teams_count=_subquery_aggregate(
            Team.objects.filter(is_active=True), Count('id')
        ),
        pending_invitations_count=_subquery_aggregate(
            Invitation.objects.filter(is_active=True).filter_pending(), Count('id')
        ),
        storage_bytes=_subquery_aggregate(
            StoredFile.objects.filter(is_active=True), Sum('size')
        ),
    )


def users_queryset() -> QuerySet:
    return User.objects.annotate(
        organizations_count=_subquery_aggregate(
            _active_members().filter(organization__is_active=True),
            Count('id'),
            field='user',
        ),
    ).order_by('-date_joined', '-id')


def overview(*, now: datetime) -> dict:
    organizations = Organization.objects.filter(is_active=True)
    users = User.objects.filter(is_active=True)
    active_since = now - timedelta(days=PLATFORM_ACTIVE_ORGANIZATION_DAYS)
    organization_counts = organizations.aggregate(
        organizations_total=Count('id'),
        organizations_suspended=Count(
            'id', filter=Q(status=OrganizationStatusChoices.SUSPENDED)
        ),
        **{
            f'organizations_new_{days}d': Count(
                'id', filter=Q(created_at__gte=now - timedelta(days=days))
            )
            for days in PLATFORM_NEW_RECORDS_DAYS
        },
    )
    user_counts = users.aggregate(
        users_total=Count('id'),
        users_blocked=Count('id', filter=Q(blocked_at__isnull=False)),
        **{
            f'users_new_{days}d': Count(
                'id', filter=Q(date_joined__gte=now - timedelta(days=days))
            )
            for days in PLATFORM_NEW_RECORDS_DAYS
        },
    )
    organizations_active = (
        organizations.filter(
            members__is_active=True,
            members__last_login_at__gte=active_since,
        )
        .distinct()
        .count()
    )
    return {
        **organization_counts,
        **user_counts,
        'organizations_active_30d': organizations_active,
    }
