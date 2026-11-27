from apps.accounts.access import Action, authorize
from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member


class BillingPermission(OrganizationScopedPermission):
    """Read access to the organization's plan and usage (Owner and Admin)."""

    def has_permission(self, request, view):
        return super().has_permission(request, view) and authorize(
            get_member(request), Action.BILLING_READ
        )


class BillingManagePermission(OrganizationScopedPermission):
    """Owner-only billing writes (BR-13)."""

    def has_permission(self, request, view):
        return super().has_permission(request, view) and authorize(
            get_member(request), Action.BILLING_MANAGE
        )
