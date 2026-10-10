from django.utils.translation import gettext_lazy
from django_filters.rest_framework import filters, filterset

from apps.accounts.mixins.filters import FilterSetMixin
from apps.accounts.models.organization import Organization, OrganizationImage


class OrganizationImageFilter(FilterSetMixin, filterset.FilterSet):
    organization = filters.ModelChoiceFilter(
        field_name='profile__organization',
        queryset=Organization.objects.filter_actives(),
        label=gettext_lazy('Organization'),
        help_text=gettext_lazy('Filter by organization'),
    )

    class Meta:
        model = OrganizationImage
        fields = {
            'image_type': ['exact'],
        }
        options_extra_kwargs = {
            'organization': {'organization_lookup': 'id', 'label_field_name': 'name'},
        }
