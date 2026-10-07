from apps.accounts.mixins.requests import OrganizationScopedRequestMixin
from apps.accounts.serializers.options import (
    OptionsOrganizationFilterSetSerializer,
    OptionsOrganizationModelSerializer,
)
from apps.accounts.utils.files import file_too_large_error, max_upload_request_size
from apps.generics.mixins.views import (
    OptionsModelMixin,
    OptionsModelViewSetMetaclass,
    OrderableModelViewSetMetaclass,
)


class ModelViewSetMetaclass(
    OptionsModelViewSetMetaclass,
    OrderableModelViewSetMetaclass,
):
    """
    Combine the orderable filter and options metaclasses.

    ``OptionsModelViewSetMetaclass`` comes first so ``OrderableModelViewSetMetaclass``
    runs inside its ``super().__new__``: the ``order_by`` filter already exists when
    the filter options are built.
    """


class OptionsOrganizationModelMixin(OptionsModelMixin):
    """Options mixin with organization and active scoping on relations."""

    options_serializer_class = OptionsOrganizationModelSerializer
    options_filterset_serializer_class = OptionsOrganizationFilterSetSerializer


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


class UploadSizeLimitMixin:
    """Reject oversized uploads from ``Content-Length`` before parsing the body."""

    upload_error_path = ('file',)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        try:
            content_length = int(request.META.get('CONTENT_LENGTH') or 0)
        except ValueError:
            content_length = 0
        if content_length > max_upload_request_size():
            raise file_too_large_error(path=self.upload_error_path)
