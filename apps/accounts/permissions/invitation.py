from rest_framework.permissions import IsAuthenticated

from apps.accounts.access import Action, authorize
from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member


class InvitationPermission(OrganizationScopedPermission):
    def has_permission(self, request, view):
        """Check if the user has permission to access the view."""
        return super().has_permission(request, view) and authorize(
            get_member(request), Action.INVITATION_MANAGE
        )

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        return authorize(get_member(request), Action.INVITATION_CHANGE, obj)


class InvitationAcceptDeclinePermission(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        return super().has_object_permission(request=request, view=view, obj=obj) and (
            (
                obj.email
                and request.user.email_verified
                and request.user.email.casefold() == obj.email.casefold()
                and obj.member_id is None
            )
            or (obj.member_id and obj.member == get_member(request))
            or (obj.user_id is not None and obj.user_id == request.user.id)
        )
