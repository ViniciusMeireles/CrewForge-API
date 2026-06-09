from rest_framework import permissions
from rest_framework.permissions import BasePermission, IsAuthenticated

from apps.accounts.utils.requests import (
    get_member,
    get_organization_id,
    is_same_organization_scope,
)


class IsActiveMember(IsAuthenticated):
    """Permission that requires an authenticated active member in session scope."""

    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and (member := get_member(request))
            and member.is_active
        )

    def has_object_permission(self, request, view, obj):
        return (
            super().has_object_permission(request, view, obj)
            and (member := get_member(request))
            and member.is_active
        )


class OrganizationScopedPermission(IsActiveMember):
    """Base permission for objects that belong to the authenticated organization."""

    organization_lookup = 'organization_id'

    @classmethod
    def get_request_member(cls, request):
        return get_member(request)

    @classmethod
    def get_session_organization_id(cls, request):
        return get_organization_id(request)

    @classmethod
    def has_organization_scope(cls, request, obj) -> bool:
        organization_id = cls.get_session_organization_id(request)
        return is_same_organization_scope(
            obj=obj,
            organization_id=organization_id,
            lookup=cls.organization_lookup,
        )

    def has_object_permission(self, request, view, obj):
        return super().has_object_permission(
            request, view, obj
        ) and self.has_organization_scope(request, obj)


class OrganizationAdminObjPermission(BasePermission):
    """Free read for any authenticated active member; write requires admin+ role."""

    def has_object_permission(self, request, view, obj):
        if not IsActiveMember().has_object_permission(request, view, obj):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        auth_member = get_member(request)
        return bool(auth_member and auth_member.has_admin_permission)
