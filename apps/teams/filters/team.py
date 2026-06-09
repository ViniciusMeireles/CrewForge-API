from django_filters.rest_framework import filterset

from apps.accounts.mixins.filters import FilterSetMixin
from apps.teams.models.team import Team


class TeamFilter(FilterSetMixin, filterset.FilterSet):
    """Filter for the Team model."""

    class Meta:
        model = Team
        fields = {
            'name': ['exact', 'icontains'],
            'slug': ['exact', 'icontains'],
            'organization': ['exact'],
            'is_active': ['exact'],
        }
