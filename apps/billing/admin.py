from django.contrib import admin

from apps.billing.models.billing_profile import BillingProfile
from apps.billing.models.gateway_event import GatewayEvent
from apps.billing.models.invoice import Invoice
from apps.billing.models.plan import Plan
from apps.billing.models.subscription import Subscription


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Plan)
class PlanAdmin(ReadOnlyAdmin):
    list_display = ('code', 'name', 'is_default', 'is_free', 'is_public', 'is_active')


@admin.register(Subscription)
class SubscriptionAdmin(ReadOnlyAdmin):
    list_display = (
        'organization',
        'plan',
        'status',
        'cycle',
        'current_period_end',
        'trial_ends_at',
        'courtesy',
    )
    list_filter = ('status', 'plan', 'courtesy')
    search_fields = ('organization__name',)
    raw_id_fields = ('organization',)


@admin.register(Invoice)
class InvoiceAdmin(ReadOnlyAdmin):
    list_display = (
        'gateway_id',
        'subscription',
        'kind',
        'amount',
        'due_date',
        'status',
    )
    list_filter = ('status', 'kind', 'gateway')
    search_fields = ('gateway_id', 'subscription__organization__name')
    raw_id_fields = ('subscription',)


@admin.register(BillingProfile)
class BillingProfileAdmin(ReadOnlyAdmin):
    list_display = ('organization', 'legal_name', 'masked_tax_id', 'city', 'state')
    search_fields = ('organization__name', 'legal_name')
    exclude = ('tax_id',)
    readonly_fields = ('masked_tax_id',)
    raw_id_fields = ('organization',)


@admin.register(GatewayEvent)
class GatewayEventAdmin(ReadOnlyAdmin):
    list_display = ('gateway', 'event_id', 'event_type', 'received_at', 'processed_at')
    list_filter = ('gateway', 'event_type')
    search_fields = ('event_id',)
