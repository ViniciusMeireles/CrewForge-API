from rest_framework import permissions

from apps.accounts.access import Action, authorize
from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member


class TeamMemberPermission(OrganizationScopedPermission):
    """
    Reading is open to the organization. A member may remove themselves (leave
    the team). Editing or removing someone else requires managing the team
    (organization manager+ or team owner/admin) and being allowed to assign the
    target's current role, so a team admin cannot touch owners or admins.
    """

    organization_lookup = 'team.organization_id'

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True

        action = (
            Action.TEAM_MEMBER_REMOVE
            if request.method == 'DELETE'
            else Action.TEAM_MEMBER_CHANGE
        )
        return authorize(get_member(request), action, obj)
