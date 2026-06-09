from django_filters.rest_framework import backends
from rest_framework import viewsets
from rest_framework.parsers import FormParser, MultiPartParser

from apps.accounts.filters.organization_image import OrganizationImageFilter
from apps.accounts.mixins.views import ModelViewSetMixin
from apps.accounts.models.organization import OrganizationImage
from apps.accounts.permissions.organization_image import OrganizationImagePermission
from apps.accounts.serializers.organization_image import OrganizationImageSerializer
from apps.generics.utils.schema import extend_schema_model_view_set


@extend_schema_model_view_set(model=OrganizationImage)
class OrganizationImageViewSet(ModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = OrganizationImageSerializer
    queryset = OrganizationImage.objects.select_related(
        'profile', 'image'
    ).filter_actives()
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'options']
    permission_classes = [OrganizationImagePermission]
    filterset_class = OrganizationImageFilter
    filter_backends = [backends.DjangoFilterBackend]
    label_expression = OrganizationImage.label_expression()
    parser_classes = [MultiPartParser, FormParser]
