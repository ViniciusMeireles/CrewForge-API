from rest_framework import permissions

from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member


class TeamMemberPermission(OrganizationScopedPermission):
    organization_lookup = 'team.organization_id'

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        auth_member = get_member(request)
        return request.method in permissions.SAFE_METHODS or (
            auth_member
            and (auth_member.id == obj.member_id or auth_member.has_manager_permission)
        )
