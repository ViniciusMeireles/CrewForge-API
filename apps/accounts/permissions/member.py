from rest_framework import permissions

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member


class MemberPermission(OrganizationScopedPermission):
    """
    Custom permission to check if the user has permission to perform actions on members.
    """

    def has_permission(self, request, view):
        if view.action == 'create_with_invite':
            return True
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        auth_member = get_member(request)
        if (
            request.method in permissions.SAFE_METHODS
            or (request.user.id == obj.user_id and obj.is_active)
            or (auth_member.has_admin_permission and request.method == 'DELETE')
        ):
            return True

        if (
            auth_member != obj
            and not auth_member.has_admin_permission
            and request.method in ['PUT', 'PATCH']
        ):
            return False

        return (
            obj.role == MemberRoleChoices.OWNER and auth_member.has_owner_permission
        ) or (obj.role != MemberRoleChoices.OWNER and auth_member.has_admin_permission)
