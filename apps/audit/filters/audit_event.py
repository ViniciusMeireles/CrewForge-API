from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import filters, filterset
from rest_framework.exceptions import ValidationError

from apps.accounts.mixins.filters import FilterSetMixin
from apps.accounts.models.member import Member
from apps.audit.models.audit_event import AuditEvent


class AuditEventFilter(FilterSetMixin, filterset.FilterSet):
    """Filter for the AuditEvent model."""

    created_at = filters.DateFromToRangeFilter()
    actor = filters.ModelChoiceFilter(
        field_name='actor_member',
        queryset=Member.objects.all(),
        label=_('Actor'),
    )

    class Meta:
        model = AuditEvent
        fields = {
            'action': ['exact', 'in'],
            'target_type': ['exact', 'in'],
            'target_id': ['exact'],
        }
        options_extra_kwargs = {
            'actor': {'label_field_name': Member.label_expression()},
        }

    def filter_queryset(self, queryset):
        data = self.form.cleaned_data
        period = data.get('created_at')
        if period and period.start and period.stop and period.start > period.stop:
            raise ValidationError(
                {'created_at': [_('The start date must be before the end date.')]}
            )
        if data.get('target_id') and not (
            data.get('target_type') or data.get('target_type__in')
        ):
            raise ValidationError(
                {'target_id': [_('Filter by target type together with target ID.')]}
            )
        return super().filter_queryset(queryset)
