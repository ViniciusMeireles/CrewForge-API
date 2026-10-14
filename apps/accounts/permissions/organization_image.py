from rest_framework import permissions

from apps.accounts.models.organization import OrganizationImage
from apps.accounts.permissions.files import StoredFilePermission
from apps.accounts.permissions.generics import OrganizationAdminObjPermission
from apps.accounts.utils.requests import (
    get_member,
    get_organization_id,
    is_same_organization_scope,
)


class OrganizationImagePermission(permissions.BasePermission):
    organization_lookup = 'profile.organization_id'

    def has_permission(self, request, view) -> bool:
        if not StoredFilePermission().has_permission(request=request, view=view):
            return False
        if request.method.upper() == 'POST':
            return get_member(request).has_admin_permission
        return True

    def has_object_permission(self, request, view, obj: OrganizationImage) -> bool:
        if not StoredFilePermission().has_object_permission(request, view, obj.image):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        if not OrganizationAdminObjPermission().has_object_permission(
            request, view, obj
        ):
            return False
        return is_same_organization_scope(
            obj=obj,
            organization_id=get_organization_id(request),
            lookup=self.organization_lookup,
        )
