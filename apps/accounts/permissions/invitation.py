from rest_framework.permissions import IsAuthenticated

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member


class InvitationPermission(OrganizationScopedPermission):
    def has_permission(self, request, view):
        """Check if the user has permission to access the view."""
        return (
            super().has_permission(request, view)
            and get_member(request).has_admin_permission
        )

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        if not (auth_member := get_member(request)):
            return False
        return auth_member.has_owner_permission or (
            obj.role in [MemberRoleChoices.MANAGER, MemberRoleChoices.MEMBER]
            and auth_member.has_admin_permission
        )


class InvitationAcceptDeclinePermission(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        return super().has_object_permission(request=request, view=view, obj=obj) and (
            (obj.email and request.user.email == obj.email and obj.member_id is None)
            or (obj.member_id and obj.member == get_member(request))
        )
