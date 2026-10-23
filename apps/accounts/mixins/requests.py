from django.contrib.auth import get_user_model
from django.utils.functional import cached_property

from apps.accounts.exceptions import OrganizationSuspended
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.accounts.utils.requests import (
    clear_suspended_organization_context,
    get_member,
    get_organization,
    get_organization_id,
)
from apps.accounts.utils.security_log import log_security_event
from apps.generics.mixins.mixins import RequestUserMixin

User = get_user_model()


class OrganizationScopedRequestMixin(RequestUserMixin):
    """
    Mixin for views to add user, member, and organization properties.

    Requests made while the session's Organization is suspended are refused with
    ``ORGANIZATION_SUSPENDED`` (and the context is dropped) before the permission
    checks, except for the user-level actions listed in
    ``organization_context_exempt_actions``.
    """

    organization_context_exempt_actions: tuple[str, ...] = ()

    def check_permissions(self, request):
        exempt = self.organization_context_exempt_actions
        if getattr(self, 'action', None) not in exempt:
            self.refuse_suspended_organization_context(request)
        super().check_permissions(request)

    def refuse_suspended_organization_context(self, request) -> None:
        if organization_id := clear_suspended_organization_context(request):
            log_security_event(
                'organization.suspended_context_refused',
                request,
                organization_id=organization_id,
            )
            raise OrganizationSuspended()

    @cached_property
    def auth_member(self) -> Member | None:
        """Get the member from the context."""
        return get_member(self.request)

    @cached_property
    def auth_organization(self) -> Organization | None:
        """Get the organization from the context."""
        return get_organization(self.request)

    @cached_property
    def auth_organization_id(self) -> int | None:
        """Get the organization ID from the context."""
        return get_organization_id(self.request)
