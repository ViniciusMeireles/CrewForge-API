from django.contrib import admin

from apps.audit.models.audit_event import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'organization',
        'action',
        'actor_label',
        'target_label',
    )
    list_filter = ('action', 'actor_type')
    search_fields = ('actor_label', 'target_label', 'target_id')
    raw_id_fields = (
        'organization',
        'actor_user',
        'actor_member',
        'subject_user',
        'impersonator',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
