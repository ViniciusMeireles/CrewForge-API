from rest_framework import permissions

from apps.accounts.access import Action, authorize
from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member


class TeamPermission(OrganizationScopedPermission):
    """
    Custom permission to check if the user has permission to perform actions on teams.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        action = (
            Action.TEAM_READ
            if request.method in permissions.SAFE_METHODS
            else Action.TEAM_WRITE
        )
        return authorize(get_member(request), action)

    def has_object_permission(self, request, view, obj):
        return super().has_object_permission(request, view, obj) and (
            request.method in permissions.SAFE_METHODS
            or authorize(get_member(request), Action.TEAM_WRITE)
        )
