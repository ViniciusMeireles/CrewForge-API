from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member


class AuditEventPermission(OrganizationScopedPermission):
    """Read access to the organization audit trail (Owner and Admin)."""

    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and get_member(request).has_audit_access
        )
