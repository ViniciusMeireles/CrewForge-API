from apps.accounts.mixins.requests import OrganizationScopedRequestMixin
from apps.accounts.serializers.options import OptionsOrganizationModelSerializer
from apps.generics.mixins.views import (
    OptionsModelMixin,
    OptionsModelViewSetMetaclass,
    OrderableModelViewSetMetaclass,
)


class ModelViewSetMetaclass(
    OrderableModelViewSetMetaclass,
    OptionsModelViewSetMetaclass,
):
    """Combine the orderable filter and form-options metaclasses."""


class OptionsOrganizationModelMixin(OptionsModelMixin):
    """Form-options mixin with organization and active scoping on relations."""

    options_serializer_class = OptionsOrganizationModelSerializer


class ModelViewSetMixin(
    OptionsOrganizationModelMixin,
    OrganizationScopedRequestMixin,
    metaclass=ModelViewSetMetaclass,
):
    """Mixin for views to add user, member, and organization properties."""

    def perform_destroy(self, instance):
        if hasattr(instance, 'is_active'):
            instance.inactivate()
        else:
            super().perform_destroy(instance)


class OrganizationScopedViewSetMixin(OrganizationScopedRequestMixin):
    organization_filter = 'organization_id'
    base_filters = {}

    def get_base_queryset_filters(self) -> dict:
        return dict(self.base_filters)

    def get_organization_filter_kwargs(self) -> dict:
        return {self.organization_filter: self.auth_organization_id}

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                **self.get_organization_filter_kwargs(),
                **self.get_base_queryset_filters(),
            )
        )
