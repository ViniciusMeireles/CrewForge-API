from django.db.models import Case, IntegerField, Value, When
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import filters, filterset

from apps.accounts.mixins.filters import FilterSetMixin
from apps.accounts.models.member import Member
from apps.generics.utils.filters import StableOrderingFilter
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.models.team_member import TeamMember

ROLE_RANK_FIELD = '_role_rank'
ROLE_RANK = Case(
    When(role=TeamMemberRoleChoices.OWNER, then=Value(0)),
    When(role=TeamMemberRoleChoices.ADMIN, then=Value(1)),
    When(role=TeamMemberRoleChoices.MANAGER, then=Value(2)),
    default=Value(3),
    output_field=IntegerField(),
)


class TeamMemberOrderingFilter(StableOrderingFilter):
    """Ordering by member name/email, joining date and role hierarchy (owner first)."""

    def filter(self, qs, value):
        if value and any(param.lstrip('-') == 'role' for param in value):
            qs = qs.annotate(**{ROLE_RANK_FIELD: ROLE_RANK})
        return super().filter(qs, value)


class TeamMemberFilter(FilterSetMixin, filterset.FilterSet):
    """Filter for the Team Member model."""

    member_full_name__icontains = filters.CharFilter(
        field_name='member__user__full_name',
        lookup_expr='icontains',
    )
    member_email__icontains = filters.CharFilter(
        field_name='member__user__email',
        lookup_expr='icontains',
    )
    team_name = filters.CharFilter(
        field_name='team__name',
        lookup_expr='exact',
    )
    team_name__icontains = filters.CharFilter(
        field_name='team__name',
        lookup_expr='icontains',
    )
    team_slug = filters.CharFilter(
        field_name='team__slug',
        lookup_expr='exact',
    )
    team_slug__icontains = filters.CharFilter(
        field_name='team__slug',
        lookup_expr='icontains',
    )
    order_by = TeamMemberOrderingFilter(
        fields={
            'member__user__full_name': 'member_name',
            'member__user__email': 'member_email',
            ROLE_RANK_FIELD: 'role',
            'created_at': 'created_at',
            'id': 'id',
        },
        field_labels={
            'member__user__full_name': _('Member name'),
            'member__user__email': _('Member email'),
            ROLE_RANK_FIELD: _('Role'),
            'created_at': _('Joined at'),
            'id': _('ID'),
        },
    )

    class Meta:
        model = TeamMember
        fields = {
            'team': ['exact'],
            'member': ['exact'],
            'is_active': ['exact'],
            'role': ['exact', 'in'],
        }
        options_extra_kwargs = {
            'team': {'label_field_name': 'name'},
            'member': {'label_field_name': Member.label_expression()},
        }
