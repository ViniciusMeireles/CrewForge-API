from rest_framework.permissions import BasePermission


def _is_active_user(user) -> bool:
    return bool(user and user.is_authenticated and user.is_active)


class IsPlatformStaff(BasePermission):
    def has_permission(self, request, view) -> bool:
        return _is_active_user(request.user) and request.user.is_platform_staff


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view) -> bool:
        return _is_active_user(request.user) and request.user.is_platform_admin
