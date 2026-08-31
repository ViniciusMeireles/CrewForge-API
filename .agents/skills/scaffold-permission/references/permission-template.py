from django.contrib.auth import decorators
from rest_framework import permissions

from apps.accounts.permissions.generics import OrganizationScopedPermission, IsActiveMember
from apps.accounts.utils.requests import get_member


# ============================================================
# PATTERN 1: Owner-only write
# ============================================================

class OwnerOnlyPermission(OrganizationScopedPermission):
    """
    Read: all authenticated members
    Write: owner only
    """

    def has_permission(self, request, view):
        auth_member = get_member(request)
        return super().has_permission(request, view) and (
            request.method in permissions.SAFE_METHODS
            or (auth_member and auth_member.has_owner_permission)
        )

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        auth_member = get_member(request)
        if not auth_member:
            return False
        return auth_member.has_owner_permission


# ============================================================
# PATTERN 2: Admin+ write (TeamPermission reference)
# ============================================================

class AdminPlusPermission(OrganizationScopedPermission):
    """
    Read: all authenticated members
    Write: admin+
    """

    def has_permission(self, request, view):
        auth_member = get_member(request)
        return super().has_permission(request, view) and (
            request.method in permissions.SAFE_METHODS
            or (auth_member and auth_member.has_admin_permission)
        )

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        auth_member = get_member(request)
        if not auth_member:
            return False
        if auth_member.has_manager_permission:
            return True
        # Team-specific: check team-level role
        auth_member_team = auth_member.teams.filter(team_id=obj.id, is_active=True).get_or_none()
        return bool(auth_member_team) and auth_member_team.has_admin_permission


# ============================================================
# PATTERN 3: Manager+ write
# ============================================================

class ManagerPlusPermission(OrganizationScopedPermission):
    """
    Read: all authenticated members
    Write: manager+
    """

    def has_permission(self, request, view):
        auth_member = get_member(request)
        return super().has_permission(request, view) and (
            request.method in permissions.SAFE_METHODS
            or (auth_member and auth_member.has_manager_permission)
        )

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        auth_member = get_member(request)
        if not auth_member:
            return False
        return auth_member.has_manager_permission


# ============================================================
# PATTERN 4: Self-or-admin (MemberPermission reference)
# ============================================================

class SelfOrAdminPermission(OrganizationScopedPermission):
    """
    Read: all authenticated members
    Update: self or admin
    Delete: admin only
    """

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False
        auth_member = get_member(request)
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.id == obj.user_id and obj.is_active:
            return True
        if auth_member.has_admin_permission and request.method == 'DELETE':
            return True
        if auth_member != obj and not auth_member.has_admin_permission:
            return False
        return True


# ============================================================
# PATTERN 5: Custom organization_lookup (TeamMemberPermission)
# ============================================================

class CustomLookupPermission(OrganizationScopedPermission):
    """
    Uses organization_lookup = 'team__organization_id' for FK traversal.
    """
    organization_lookup = 'team__organization_id'

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False
        auth_member = get_member(request)
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(auth_member and (
            auth_member.id == obj.member_id
            or auth_member.has_manager_permission
        ))
