from django.contrib.auth import get_user_model
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import filters, filterset
from rest_framework.exceptions import ValidationError

from apps.accounts.choices import OrganizationStatusChoices, PlatformRoleChoices
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.audit.models.audit_event import AuditEvent
from apps.generics.utils.filters import StableOrderingFilter

User = get_user_model()

PERIOD_ERROR = _('The start date must be before the end date.')


class PeriodValidationMixin:
    period_fields: tuple[str, ...] = ()

    def filter_queryset(self, queryset):
        data = self.form.cleaned_data
        for name in self.period_fields:
            period = data.get(name)
            if period and period.start and period.stop and period.start > period.stop:
                raise ValidationError({name: [PERIOD_ERROR]})
        return super().filter_queryset(queryset)


class DeletedFilterMixin:
    def filter_queryset(self, queryset):
        if not self.form.cleaned_data.get('deleted'):
            queryset = queryset.filter(is_active=True)
        return super().filter_queryset(queryset)


class PlatformOrganizationFilter(
    PeriodValidationMixin, DeletedFilterMixin, filterset.FilterSet
):
    period_fields = ('created_at',)

    search = filters.CharFilter(method='filter_search', label=_('Search'))
    status = filters.ChoiceFilter(choices=OrganizationStatusChoices.choices)
    created_at = filters.DateFromToRangeFilter()
    deleted = filters.BooleanFilter(method='filter_noop', label=_('Include deleted'))
    order_by = StableOrderingFilter(
        fields=(
            ('name', 'name'),
            ('created_at', 'created_at'),
            ('last_access_at', 'last_access_at'),
            ('active_members_count', 'active_members_count'),
        ),
    )

    class Meta:
        model = Organization
        fields = ['search', 'status', 'created_at', 'deleted']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(slug__icontains=value)
            | Q(owner__user__email__icontains=value)
        )

    def filter_noop(self, queryset, name, value):
        return queryset


class PlatformUserFilter(
    PeriodValidationMixin, DeletedFilterMixin, filterset.FilterSet
):
    period_fields = ('date_joined',)

    search = filters.CharFilter(method='filter_search', label=_('Search'))
    verified = filters.BooleanFilter(method='filter_verified', label=_('Verified'))
    blocked = filters.BooleanFilter(method='filter_blocked', label=_('Blocked'))
    platform_role = filters.ChoiceFilter(choices=PlatformRoleChoices.choices)
    date_joined = filters.DateFromToRangeFilter()
    deleted = filters.BooleanFilter(method='filter_noop', label=_('Include deleted'))
    order_by = StableOrderingFilter(
        fields=(
            ('full_name', 'full_name'),
            ('date_joined', 'date_joined'),
            ('last_login', 'last_login'),
        ),
    )

    class Meta:
        model = User
        fields = ['search', 'verified', 'blocked', 'platform_role', 'date_joined']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(full_name__icontains=value)
            | Q(email__icontains=value)
            | Q(username__icontains=value)
        )

    def filter_verified(self, queryset, name, value):
        return queryset.filter(email_verified_at__isnull=not value)

    def filter_blocked(self, queryset, name, value):
        return queryset.filter(blocked_at__isnull=not value)

    def filter_noop(self, queryset, name, value):
        return queryset


class PlatformMemberFilter(filterset.FilterSet):
    search = filters.CharFilter(method='filter_search', label=_('Search'))
    is_active = filters.BooleanFilter()
    exclude_owner = filters.BooleanFilter(
        method='filter_exclude_owner', label=_('Exclude owner')
    )

    class Meta:
        model = Member
        fields = ['search', 'is_active', 'exclude_owner']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(user__full_name__icontains=value)
            | Q(user__email__icontains=value)
            | Q(nickname__icontains=value)
        )

    def filter_exclude_owner(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.exclude(owned_organizations__id=F('organization_id'))


class PlatformAuditEventFilter(PeriodValidationMixin, filterset.FilterSet):
    period_fields = ('created_at',)
    scope_account = 'account'
    scope_organization = 'organization'

    created_at = filters.DateFromToRangeFilter()
    organization = filters.ModelChoiceFilter(
        queryset=Organization.objects.all(), label=_('Organization')
    )
    user = filters.NumberFilter(method='filter_user', label=_('User'))
    scope = filters.ChoiceFilter(
        method='filter_scope',
        label=_('Scope'),
        choices=(
            (scope_account, _('Account')),
            (scope_organization, _('Organization')),
        ),
    )

    class Meta:
        model = AuditEvent
        fields = {
            'action': ['exact', 'in'],
            'target_type': ['exact', 'in'],
        }

    def filter_user(self, queryset, name, value):
        return queryset.filter(Q(actor_user_id=value) | Q(subject_user_id=value))

    def filter_scope(self, queryset, name, value):
        return queryset.filter(organization__isnull=value == self.scope_account)
