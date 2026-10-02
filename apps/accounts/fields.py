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

    The active filter applies when the related model has ``is_active``. The
    organization filter uses ``organization_id`` or the ``organization_lookup``
    declared for the field; ``OptionsOrganizationModelSerializer`` refuses
    relations that have neither.

    Text search defaults to ``unaccent__icontains``: case- and accent-insensitive.
    The ``unaccent`` lookup (``django.contrib.postgres``) is bilateral, so both the
    column and the searched value go through PostgreSQL ``unaccent()``.
    """

    filter_lookup_expr = 'unaccent__icontains'
