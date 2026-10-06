from django_filters.rest_framework import filterset

from apps.accounts.mixins.filters import FilterSetMixin
from apps.accounts.models.invitation import Invitation
from apps.accounts.serializers.options import assignable_role_choices


class InvitationFilter(FilterSetMixin, filterset.FilterSet):
    """Filter for the Invitation model."""

    class Meta:
        model = Invitation
        fields = {
            'email': ['exact', 'icontains'],
            'is_accepted': ['exact'],
            'is_expired': ['exact'],
            'is_declined': ['exact'],
            'expired_at': ['exact', 'gt', 'lt'],
            'role': ['exact', 'in'],
        }
        options_extra_kwargs = {
            'role': {'choices_filter': assignable_role_choices},
            'role__in': {'choices_filter': assignable_role_choices},
        }


class InvitationAcceptanceFilter(InvitationFilter):
    class Meta(InvitationFilter.Meta):
        fields = dict(InvitationFilter.Meta.fields, **{'key': ['exact']})
        options_extra_kwargs = {}
