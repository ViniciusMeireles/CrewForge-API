from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from nested_admin import NestedModelAdmin, NestedStackedInline, NestedTabularInline

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.forms.files import StoredFileModelForm
from apps.accounts.models.files import StoredFile
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.accounts.models.organization import (
    Organization,
    OrganizationImage,
    OrganizationProfile,
)
from apps.accounts.utils.platform_role import set_platform_role


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
    search_fields = ('name', 'slug')
    list_filter = ('is_active', 'status')

    def get_queryset(self, request):
        return super().get_queryset(request).with_owner()

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(
            request, queryset, search_term
        )
        if search_term:
            owners = Member.objects.filter(
                role=MemberRoleChoices.OWNER,
                is_active=True,
                user__email__icontains=search_term,
            ).values('organization_id')
            queryset |= self.get_queryset(request).filter(pk__in=owners)
        return queryset, may_have_duplicates

    readonly_fields = (
        'slug',
        'status',
        'suspended_at',
        'suspended_by',
        'suspension_reason',
    )
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
        'status',
        'created_at',
    )
    list_filter = ('status', 'role', 'organization')
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
        'platform_role',
        'is_active',
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'platform_role', 'is_active')

    def save_model(self, request, obj, form, change):
        role = obj.platform_role
        if change and 'platform_role' in form.changed_data:
            obj.platform_role = form.initial['platform_role']
            super().save_model(request, obj, form, change)
            set_platform_role(obj, role, request=request)
            return
        super().save_model(request, obj, form, change)


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
