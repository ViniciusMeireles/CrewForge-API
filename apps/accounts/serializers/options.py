from django.core.exceptions import FieldError, ImproperlyConfigured

from apps.accounts.fields import PaginatedOptionsActiveOrganizationSerializer
from apps.generics.fields.options import PaginatedOptionsBaseSerializer
from apps.generics.serializers.options import (
    OPTIONS_FIELD_KWARGS,
    OptionsFilterSetSerializer,
    OptionsModelSerializer,
)


class OrganizationScopedOptionsSerializerMixin:
    """
    Scope the relations of an options serializer to the session organization.

    Every relation must be scopable: the related model has ``organization_id``, or
    the field declares the path with ``organization_lookup`` in
    ``Meta.options_extra_kwargs`` of the source serializer or filterset (e.g.
    ``{'owner': {'organization_lookup': 'members__organization_id'}}``). Otherwise
    it would list records from every tenant, so building the field raises
    ``ImproperlyConfigured`` (at class creation, through the ViewSet metaclass)
    unless it is explicitly declared global with
    ``{'<field>': {'organization_scoped': False}}``.
    """

    serializer_related_field = PaginatedOptionsActiveOrganizationSerializer
    options_field_kwargs = OPTIONS_FIELD_KWARGS | {
        'organization_lookup',
        'organization_filters',
    }
    options_meta_kwargs = frozenset({'organization_scoped'})

    def get_fields(self):
        fields = super().get_fields()
        extra_kwargs = self.get_extra_kwargs()
        for field_name, field in fields.items():
            if isinstance(field, PaginatedOptionsBaseSerializer):
                self.check_organization_scope(
                    field_name, field, extra_kwargs.get(field_name, {})
                )
        return fields

    def check_organization_scope(
        self, field_name: str, field: PaginatedOptionsBaseSerializer, kwargs: dict
    ) -> None:
        """Raise ``ImproperlyConfigured`` when the field cannot be scoped."""
        model = field.queryset.model
        label = f'{self.__class__.__name__}.{field_name}'
        if lookup := field.get_organization_lookup(model):
            filters = field.get_organization_filters(model)
            try:
                model._default_manager.filter(**{lookup: 0}, **filters)
            except FieldError as exc:
                raise ImproperlyConfigured(
                    f'{label}: invalid organization_lookup {lookup!r} or '
                    f'organization_filters {filters!r} for {model.__name__}: {exc}'
                ) from exc
            return
        if kwargs.get('organization_scoped') is False:
            return
        raise ImproperlyConfigured(
            f'{label}: options for {model.__name__} cannot be scoped to the '
            'session organization (the model has no organization_id) and would list '
            'records from every tenant. Declare the path with '
            "Meta.options_extra_kwargs = {'"
            f"{field_name}': {{'organization_lookup': '<path>__organization_id'}}}}, "
            'disable the routes (options_actions = ()), declare the field as a nested '
            'serializer on the source, or mark it as global with '
            "{'organization_scoped': False}."
        )


class OptionsOrganizationModelSerializer(
    OrganizationScopedOptionsSerializerMixin,
    OptionsModelSerializer,
):
    """Form options with relations scoped to the session organization."""


class OptionsOrganizationFilterSetSerializer(
    OrganizationScopedOptionsSerializerMixin,
    OptionsFilterSetSerializer,
):
    """Filter options with relations scoped to the session organization."""
