from django_filters.rest_framework import filters, filterset

from apps.accounts.mixins.filters import FilterSetMixin
from apps.teams.models.team_member import TeamMember


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

    class Meta:
        model = TeamMember
        fields = {
            'team': ['exact'],
            'member': ['exact'],
            'is_active': ['exact'],
            'role': ['exact', 'in'],
        }
