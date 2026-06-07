from django_filters.rest_framework import filters, filterset

from apps.accounts.mixins.filters import FilterSetMixin
from apps.accounts.models.organization import Organization, OrganizationImage


class OrganizationImageFilter(FilterSetMixin, filterset.FilterSet):
    organization = filters.ModelChoiceFilter(
        field_name='profile__organization',
        queryset=Organization.objects.filter_actives(),
        label='Organization',
        help_text='Filter by organization',
    )

    class Meta:
        model = OrganizationImage
        fields = {
            'image_type': ['exact'],
            'is_active': ['exact'],
        }
