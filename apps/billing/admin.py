from django.contrib import admin

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
    list_display = ('organization', 'plan', 'status', 'trial_ends_at', 'courtesy')
    list_filter = ('status', 'plan', 'courtesy')
    search_fields = ('organization__name',)
    raw_id_fields = ('organization',)
