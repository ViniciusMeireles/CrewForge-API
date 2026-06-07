from rest_framework import permissions

from apps.accounts.models.organization import OrganizationImage
from apps.accounts.permissions.files import StoredFilePermission
from apps.accounts.utils.requests import get_member


class OrganizationImagePermission(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        return StoredFilePermission().has_permission(request=request, view=view)

    def has_object_permission(self, request, view, obj: OrganizationImage) -> bool:
        auth_member = get_member(request)
        return bool(
            StoredFilePermission().has_object_permission(request, view, obj.image)
            and (
                auth_member
                and auth_member.has_admin_permission
                and auth_member.organization_id == obj.profile.organization_id
                or request.method in permissions.SAFE_METHODS
            )
        )
