from django.contrib.auth import get_user_model
from django.utils.functional import cached_property

from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.accounts.utils.requests import (
    get_member,
    get_organization,
    get_organization_id,
)
from apps.generics.mixins.mixins import RequestUserMixin

User = get_user_model()


class OrganizationScopedRequestMixin(RequestUserMixin):
    """Mixin for views to add user, member, and organization properties."""

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
