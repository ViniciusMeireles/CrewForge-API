from django_filters.rest_framework import filters, filterset

from apps.accounts.mixins.filters import FilterSetMixin
from apps.accounts.models.member import Member


class MemberFilter(FilterSetMixin, filterset.FilterSet):
    """Filter for the Member model."""

    full_name__icontains = filters.CharFilter(
        field_name='user__full_name',
        lookup_expr='icontains',
    )
    email__icontains = filters.CharFilter(
        field_name='user__email',
        lookup_expr='icontains',
    )

    class Meta:
        model = Member
        fields = {
            'nickname': ['exact', 'icontains'],
            'is_active': ['exact'],
            'organization': ['exact'],
            'user': ['exact'],
            'role': ['exact', 'in'],
        }
        options_extra_kwargs = {
            'organization': {'organization_lookup': 'id', 'label_field_name': 'name'},
            'user': {
                'organization_lookup': 'members__organization_id',
                'organization_filters': {'members__is_active': True},
                'label_field_name': 'full_name',
            },
        }
