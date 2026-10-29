import logging

from django.utils.translation import gettext_lazy as _
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member
from apps.accounts.utils.security_log import log_security_event


class MemberPermission(OrganizationScopedPermission):
    """
    Custom permission to check if the user has permission to perform actions on members.
    """

    def has_permission(self, request, view):
        if view.action == 'create_with_invite':
            return True
        if not super().has_permission(request, view):
            return False
        if request.method in permissions.SAFE_METHODS:
            return get_member(request).has_members_access
        return True

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        if obj.role == MemberRoleChoices.OWNER and (
            request.method == 'DELETE' or view.action == 'update_role'
        ):
            log_security_event(
                'member.owner_protected',
                request,
                level=logging.WARNING,
                member_id=obj.pk,
            )
            raise PermissionDenied(
                _('The Owner cannot be removed or demoted; transfer ownership first.')
            )

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
