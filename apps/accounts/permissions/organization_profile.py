from rest_framework import permissions

from apps.accounts.permissions.generics import OrganizationAdminObjPermission
from apps.accounts.utils.requests import get_organization_id, is_same_organization_scope


class OrganizationProfilePermission(OrganizationAdminObjPermission):
    organization_lookup = 'organization_id'

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_same_organization_scope(
            obj=obj,
            organization_id=get_organization_id(request),
            lookup=self.organization_lookup,
        )
