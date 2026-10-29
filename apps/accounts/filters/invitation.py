from django_filters.rest_framework import filters, filterset

from apps.accounts.choices import InvitationStatusChoices
from apps.accounts.mixins.filters import FilterSetMixin
from apps.accounts.models.invitation import Invitation
from apps.accounts.serializers.options import assignable_role_choices


class InvitationFilter(FilterSetMixin, filterset.FilterSet):
    """Filter for the Invitation model."""

    status = filters.ChoiceFilter(
        choices=[
            choice
            for choice in InvitationStatusChoices.choices
            if choice[0] != InvitationStatusChoices.REVOKED
        ],
        method='filter_status',
    )
    is_accepted = filters.BooleanFilter(method='filter_is_accepted')
    is_expired = filters.BooleanFilter(method='filter_is_expired')
    is_declined = filters.BooleanFilter(method='filter_is_declined')

    class Meta:
        model = Invitation
        fields = {
            'email': ['exact', 'icontains'],
            'expired_at': ['exact', 'gt', 'lt'],
            'role': ['exact', 'in'],
        }
        options_extra_kwargs = {
            'role': {'choices_filter': assignable_role_choices},
            'role__in': {'choices_filter': assignable_role_choices},
        }

    @staticmethod
    def _by_status(queryset, status, value):
        matching = queryset.filter_effective_status(status)
        if value:
            return matching
        return queryset.exclude(pk__in=matching.values('pk'))

    def filter_status(self, queryset, name, value):
        return queryset.filter_effective_status(value)

    def filter_is_accepted(self, queryset, name, value):
        return self._by_status(queryset, InvitationStatusChoices.ACCEPTED, value)

    def filter_is_expired(self, queryset, name, value):
        return self._by_status(queryset, InvitationStatusChoices.EXPIRED, value)

    def filter_is_declined(self, queryset, name, value):
        return self._by_status(queryset, InvitationStatusChoices.DECLINED, value)


class InvitationAcceptanceFilter(InvitationFilter):
    class Meta(InvitationFilter.Meta):
        fields = dict(InvitationFilter.Meta.fields, **{'key': ['exact']})
        options_extra_kwargs = {}
