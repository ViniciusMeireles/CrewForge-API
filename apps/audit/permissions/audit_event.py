from apps.accounts.access import Action, plan_allows, role_allows
from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member
from apps.billing.exceptions import PlanFeatureUnavailableError


class AuditEventPermission(OrganizationScopedPermission):
    """Read access to the organization audit trail (Owner and Admin)."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        member = get_member(request)
        if not role_allows(member, Action.AUDIT_READ):
            return False
        if not plan_allows(member, Action.AUDIT_READ):
            raise PlanFeatureUnavailableError()
        return True
