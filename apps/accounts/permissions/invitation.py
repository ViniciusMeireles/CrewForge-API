from rest_framework import permissions

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member


class InvitationPermission(OrganizationScopedPermission):
    def has_permission(self, request, view):
        """Check if the user has permission to access the view."""
        return (
            super().has_permission(request, view)
            and get_member(request).has_admin_permission
        )

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        auth_member = get_member(request)
        return (
            request.method in permissions.SAFE_METHODS
            or (
                obj.role == MemberRoleChoices.OWNER and auth_member.has_owner_permission
            )
            or (
                obj.role == MemberRoleChoices.ADMIN and auth_member.has_admin_permission
            )
            or (
                obj.role == MemberRoleChoices.MANAGER
                and auth_member.has_manager_permission
            )
            or (
                obj.role == MemberRoleChoices.MEMBER
                and auth_member.has_member_permission
            )
        )
