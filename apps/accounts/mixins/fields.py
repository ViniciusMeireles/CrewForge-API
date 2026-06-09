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
    Mixin to filter queryset based on the organization_id field.
    """

    def get_queryset(self):
        """
        Override the get_queryset method to filter queryset based on the
        organization_id field.
        This is useful for models that have an organization_id field to filter records
        based on the organization.
        """
        queryset = super().get_queryset()
        model = queryset.model
        if hasattr(model, 'organization_id'):
            filters = {'organization_id': self.auth_organization_id}
        else:
            filters = {}
        return queryset.filter(**filters)


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
