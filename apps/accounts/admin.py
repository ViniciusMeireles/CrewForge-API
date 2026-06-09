from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms.files import StoredFileModelForm
from apps.accounts.models.files import StoredFile
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization, OrganizationImage

admin.site.register(get_user_model())
admin.site.register(Organization)
admin.site.register(OrganizationImage)
admin.site.register(Member)
admin.site.register(Invitation)


@admin.register(StoredFile)
class StoredFileAdmin(admin.ModelAdmin):
    list_display = (
        'uuid',
        'name',
        'original_name',
        'content_type',
        'size',
        'viewing_permission',
        'updating_permission',
        'owner',
        'organization',
        'is_active',
        'created_at',
        'file_url',
    )
    list_filter = (
        'content_type',
        'viewing_permission',
        'updating_permission',
        'is_active',
        'organization',
    )
    search_fields = (
        'name',
        'original_name',
        'uuid',
        'owner__username',
        'owner__email',
    )
    readonly_fields = ('uuid',)
    list_select_related = ('owner', 'organization')
    list_per_page = 50
    ordering = ('-id',)
    date_hierarchy = 'created_at'
    form = StoredFileModelForm

    @admin.display(description=_('file'))
    def file_url(self, obj):
        return format_html(
            '<a href="{}" target="_blank" class="viewlink inlineviewlink"></a>',
            obj.file_path,
        )
