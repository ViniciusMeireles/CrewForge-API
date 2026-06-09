from django_filters.rest_framework import filterset

from apps.accounts.mixins.filters import FilterSetMixin
from apps.accounts.models.organization import Organization


class OrganizationFilter(FilterSetMixin, filterset.FilterSet):
    """Filter for the Organization model."""

    class Meta:
        model = Organization
        fields = {
            'name': ['exact', 'icontains'],
            'slug': ['exact', 'icontains'],
            'is_active': ['exact'],
        }
