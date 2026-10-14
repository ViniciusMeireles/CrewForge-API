from rest_framework import permissions

from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member


class TeamPermission(OrganizationScopedPermission):
    """
    Custom permission to check if the user has permission to perform actions on teams.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        auth_member = get_member(request)
        if request.method in permissions.SAFE_METHODS:
            return auth_member.has_teams_access
        return auth_member.has_manager_permission

    def has_object_permission(self, request, view, obj):
        return super().has_object_permission(request, view, obj) and (
            request.method in permissions.SAFE_METHODS
            or get_member(request).has_manager_permission
        )
