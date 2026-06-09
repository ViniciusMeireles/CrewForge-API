from rest_framework import permissions

from apps.accounts.models.organization import Organization
from apps.accounts.utils.requests import get_member


class OrganizationPermission(permissions.BasePermission):
    """
    Custom permission to only allow owners of an organization to edit it.
    Assumes that the owner is the user who created the organization.
    """

    def has_object_permission(self, request, view, obj: Organization):
        is_member = (
            request.user
            and request.user.is_authenticated
            and request.user.members.filter(
                organization_id=obj.id,
                is_active=True,
            ).exists()
        )
        auth_member = get_member(request)
        return (
            auth_member
            and auth_member.has_owner_permission
            and auth_member.organization == obj
            or request.method in permissions.SAFE_METHODS
            or (view.action == 'login' and is_member)
        )
