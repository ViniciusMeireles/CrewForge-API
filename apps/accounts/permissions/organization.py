from rest_framework import permissions

from apps.accounts.models.organization import Organization
from apps.accounts.utils.requests import get_member


class OrganizationPermission(permissions.BasePermission):
    """
    Custom permission to only allow owners of an organization to edit it.
    Assumes that the owner is the user who created the organization.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj: Organization):
        is_member = (
            request.user.is_active
            and request.user.members.filter(
                organization_id=obj.id,
                is_active=True,
            ).exists()
        )
        if request.method in permissions.SAFE_METHODS or view.action == 'login':
            return is_member
        auth_member = get_member(request)
        return bool(
            auth_member
            and auth_member.has_owner_permission
            and auth_member.organization == obj
        )
