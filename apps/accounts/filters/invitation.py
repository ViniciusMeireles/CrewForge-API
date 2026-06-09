from django_filters.rest_framework import filterset

from apps.accounts.mixins.filters import FilterSetMixin
from apps.accounts.models.invitation import Invitation


class InvitationFilter(FilterSetMixin, filterset.FilterSet):
    """Filter for the Invitation model."""

    class Meta:
        model = Invitation
        fields = {
            'email': ['exact', 'icontains'],
            'is_accepted': ['exact'],
            'is_expired': ['exact'],
            'expired_at': ['exact', 'gt', 'lt'],
            'role': ['exact', 'in'],
        }
