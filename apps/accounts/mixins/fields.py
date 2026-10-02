from django.utils.functional import cached_property
from rest_framework import relations

from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.accounts.utils.requests import (
    get_member,
    get_organization,
    get_organization_id,
)
from apps.generics.fields.fields import AuthUserFieldMixin
from apps.generics.fields.relations import PrimaryKeyActiveRelatedFieldMixin


class OrganizationScopedFieldMixin(AuthUserFieldMixin):
    @cached_property
    def auth_member(self) -> Member | None:
        """Get the member from the context."""
        return get_member(self.context.get('request'))

    @cached_property
    def auth_organization(self) -> Organization | None:
        """Get the organization from the context."""
        return get_organization(self.context.get('request'))

    @cached_property
    def auth_organization_id(self) -> int | None:
        """Get the organization ID from the context."""
        return get_organization_id(self.context.get('request'))


class PrimaryKeyOrganizationRelatedFieldMixin(OrganizationScopedFieldMixin):
    """
    Mixin to filter the queryset by the session organization.

    By default the filter is ``organization_id`` and only applies when the related
    model has that field. Models scoped through a relation declare the path with
    the ``organization_lookup`` kwarg (e.g. ``'team__organization_id'`` or
    ``'members__organization_id'``), which is always applied.

    ``organization_filters`` adds lookups to the same ``filter()`` call as the
    organization lookup, so conditions on a to-many path apply to the same related
    row (e.g. ``{'members__is_active': True}`` with ``'members__organization_id'``
    keeps only users with an active membership in the session organization).

    Without a session organization the queryset is empty: ``<lookup>=None`` would
    match rows without an organization (``IS NULL``).
    """

    organization_lookup: str | None = None
    organization_filters: dict | None = None

    def __init__(
        self,
        *args,
        organization_lookup: str | None = None,
        organization_filters: dict | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if organization_lookup is not None:
            self.organization_lookup = organization_lookup
        if organization_filters is not None:
            self.organization_filters = dict(organization_filters)

    def get_organization_lookup(self, model) -> str | None:
        """Lookup that scopes ``model`` to the organization, or ``None``."""
        if self.organization_lookup:
            return self.organization_lookup
        if hasattr(model, 'organization_id'):
            return 'organization_id'
        return None

    def get_organization_filters(self, model) -> dict:
        """Lookups applied together with the organization lookup."""
        return dict(self.organization_filters or {})

    def get_queryset(self):
        queryset = super().get_queryset()
        if not (lookup := self.get_organization_lookup(queryset.model)):
            return queryset
        if self.auth_organization_id is None:
            return queryset.none()
        queryset = queryset.filter(
            **{lookup: self.auth_organization_id},
            **self.get_organization_filters(queryset.model),
        )
        # A lookup through a to-many relation can repeat rows.
        if '__' in lookup:
            queryset = queryset.distinct()
        return queryset


class PrimaryKeyRelatedField(
    PrimaryKeyActiveRelatedFieldMixin,
    PrimaryKeyOrganizationRelatedFieldMixin,
    relations.PrimaryKeyRelatedField,
):
    """
    Custom field to handle the primary key related field in the serializer.
    This field is used to handle the primary key related field in the serializer.
    It combines the functionality of PrimaryKeyActiveRelatedFieldMixin and
    PrimaryKeyOrganizationRelatedFieldMixin to filter the queryset based on the
    is_active field and organization_id field.
    """
