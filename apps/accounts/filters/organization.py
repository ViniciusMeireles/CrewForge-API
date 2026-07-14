from django_filters.rest_framework import filters, filterset

from apps.accounts.mixins.filters import FilterSetMixin
from apps.accounts.models.organization import Organization


class OrganizationFilter(FilterSetMixin, filterset.FilterSet):
    """Filter for the Organization model."""

    my_organizations = filters.BooleanFilter(method='filter_my_organizations')

    class Meta:
        model = Organization
        fields = {
            'name': ['exact', 'icontains'],
            'slug': ['exact', 'icontains'],
            'is_active': ['exact'],
        }

    def filter_my_organizations(self, queryset, name, value):
        if value and self.auth_user:
            return queryset.filter(
                members__user_id=self.auth_user.id,
                members__is_active=True,
                is_active=True,
            )
        return queryset
