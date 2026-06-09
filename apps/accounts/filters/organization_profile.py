from django_filters.rest_framework import filterset

from apps.accounts.mixins.filters import FilterSetMixin
from apps.accounts.models.organization import OrganizationProfile


class OrganizationProfileFilter(FilterSetMixin, filterset.FilterSet):
    class Meta:
        model = OrganizationProfile
        fields = {
            'website': ['exact', 'icontains'],
            'description': ['exact', 'icontains'],
        }
