from apps.accounts.mixins.requests import OrganizationScopedRequestMixin


class FilterSetMixin(OrganizationScopedRequestMixin):
    """Mixin for filtersets to add user, member, and organization properties."""
