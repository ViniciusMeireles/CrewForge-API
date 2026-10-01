from apps.accounts.mixins.fields import PrimaryKeyOrganizationRelatedFieldMixin
from apps.generics.fields.options import PaginatedOptionsSerializer
from apps.generics.fields.relations import PrimaryKeyActiveRelatedFieldMixin


class PaginatedActiveOptionsSerializer(
    PrimaryKeyActiveRelatedFieldMixin,
    PaginatedOptionsSerializer,
):
    """Relation options restricted to active records."""


class PaginatedOptionsOrganizationSerializer(
    PrimaryKeyOrganizationRelatedFieldMixin,
    PaginatedOptionsSerializer,
):
    """Relation options restricted to the session organization."""


class PaginatedOptionsActiveOrganizationSerializer(
    PaginatedActiveOptionsSerializer,
    PaginatedOptionsOrganizationSerializer,
):
    """
    Relation options with the same scope as the write ``PrimaryKeyRelatedField``:
    active records of the session organization.

    Each filter is applied only when the related model has the field
    (``is_active`` / ``organization_id``). Models without ``organization_id``
    (e.g. ``User``, ``Organization``) are therefore NOT tenant-scoped; ViewSets
    exposing such relations must opt out with ``options_actions = ()``.
    """
