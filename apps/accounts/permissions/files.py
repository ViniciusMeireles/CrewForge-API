from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from apps.accounts.choices import StoredFileAccess
from apps.accounts.models.files import StoredFile
from apps.accounts.utils.requests import get_member


class StoredFilePermission(BasePermission):
    def has_permission(self, request, view) -> bool:
        if request.method.upper() == 'POST':
            if not IsAuthenticated().has_permission(request=request, view=view):
                return False
            member = get_member(request=request)
            if not (member and member.is_active):
                return False
        return True

    def has_object_permission(self, request, view, obj: StoredFile) -> bool:
        if (
            isinstance(view, GenericViewSet)
            and view.action in ['update', 'partial_update', 'destroy']
        ) or request.method.upper() in ['PUT', 'PATCH', 'DELETE']:
            obj_permission = obj.updating_permission
        else:
            obj_permission = obj.viewing_permission

        if obj_permission == StoredFileAccess.PUBLIC:
            return True
        if (
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and (
                request.user.is_superuser
                or (
                    obj.owner_id == request.user.id
                    and obj_permission == StoredFileAccess.OWNER
                )
            )
        ):
            return True

        member = get_member(request=request)
        if not (member and member.is_active):
            return False
        if obj.organization_id != member.organization_id:
            return False

        return (
            (
                obj_permission == StoredFileAccess.MEMBERS_ORGANIZATION
                and member.has_member_permission
            )
            or (
                obj_permission == StoredFileAccess.MANAGERS_ORGANIZATION
                and member.has_manager_permission
            )
            or (
                obj_permission == StoredFileAccess.ADMINS_ORGANIZATION
                and member.has_admin_permission
            )
            or (
                obj_permission == StoredFileAccess.OWNERS_ORGANIZATION
                and member.has_owner_permission
            )
        )
