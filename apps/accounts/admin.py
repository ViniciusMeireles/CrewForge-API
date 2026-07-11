from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from nested_admin import NestedModelAdmin, NestedStackedInline, NestedTabularInline

from apps.accounts.forms.files import StoredFileModelForm
from apps.accounts.models.files import StoredFile
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.accounts.models.organization import (
    Organization,
    OrganizationImage,
    OrganizationProfile,
)


class OrganizationImageInline(NestedTabularInline):
    model = OrganizationImage
    fields = ('image', 'image_type')
    extra = 0


class OrganizationProfileInline(NestedStackedInline):
    model = OrganizationProfile
    fields = ('website', 'description')
    inlines = [OrganizationImageInline]


@admin.register(Organization)
class OrganizationAdmin(NestedModelAdmin):
    list_display = ('name', 'slug', 'owner', 'is_active', 'created_at')
    search_fields = ('name', 'slug', 'owner__user__email')
    list_filter = ('is_active',)
    readonly_fields = ('slug',)
    inlines = [OrganizationProfileInline]


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'nickname', 'organization', 'role', 'is_active')
    list_filter = ('role', 'is_active', 'organization')
    search_fields = ('user__email', 'user__username', 'nickname', 'organization__name')
    list_select_related = ('user', 'organization')


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        'email',
        'organization',
        'role',
        'is_accepted',
        'is_expired',
        'created_at',
    )
    list_filter = ('is_accepted', 'is_expired', 'role', 'organization')
    search_fields = ('email', 'organization__name')
    readonly_fields = ('key',)
    list_select_related = ('organization',)


@admin.register(get_user_model())
class CustomUserAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_staff',
        'is_active',
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_active')


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

    def get_form(self, request, obj=None, change=False, **kwargs):
        form_class = super().get_form(request, obj, change=change, **kwargs)

        class _StoredFileModelForm(form_class):
            def __init__(self, *args, **kwargs):
                kwargs['request'] = request
                super().__init__(*args, **kwargs)

        return _StoredFileModelForm

    @admin.display(description=_('file'))
    def file_url(self, obj):
        return format_html(
            '<a href="{}" target="_blank" class="viewlink inlineviewlink"></a>',
            obj.file_path,
        )
