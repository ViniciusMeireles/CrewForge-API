from django_filters.rest_framework import backends
from rest_framework import viewsets
from rest_framework.parsers import FormParser, MultiPartParser

from apps.accounts.filters.organization_image import OrganizationImageFilter
from apps.accounts.mixins.views import (
    ModelViewSetMixin,
    OrganizationScopedViewSetMixin,
    UploadSizeLimitMixin,
)
from apps.accounts.models.organization import OrganizationImage
from apps.accounts.permissions.organization_image import OrganizationImagePermission
from apps.accounts.serializers.organization_image import OrganizationImageSerializer
from apps.audit.choices import AuditActionChoices
from apps.generics.mixins.views import FilterOptionsMixin, FormOptionsMixin
from apps.generics.utils.filters import orderable_filter_factory
from apps.generics.utils.schema import extend_schema_model_view_set


@extend_schema_model_view_set(model=OrganizationImage)
class OrganizationImageViewSet(
    OrganizationScopedViewSetMixin,
    UploadSizeLimitMixin,
    FormOptionsMixin,
    FilterOptionsMixin,
    ModelViewSetMixin,
    viewsets.ModelViewSet,
):
    serializer_class = OrganizationImageSerializer
    organization_filter = 'profile__organization_id'
    upload_error_path = ('image', 'file')
    queryset = OrganizationImage.objects.select_related(
        'profile', 'image'
    ).filter_actives()
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']
    audit_actions = {
        'create': AuditActionChoices.ORGANIZATION_IMAGE_CREATED,
        'update': AuditActionChoices.ORGANIZATION_IMAGE_UPDATED,
        'partial_update': AuditActionChoices.ORGANIZATION_IMAGE_UPDATED,
        'destroy': AuditActionChoices.ORGANIZATION_IMAGE_DELETED,
    }
    permission_classes = [OrganizationImagePermission]
    filterset_class = orderable_filter_factory(
        OrganizationImageSerializer, OrganizationImageFilter
    )
    filter_backends = [backends.DjangoFilterBackend]
    parser_classes = [MultiPartParser, FormParser]
    # Form options are reachable without authentication: no search on them.
    options_search = False
