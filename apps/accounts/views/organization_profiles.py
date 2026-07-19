from django_filters.rest_framework import backends
from rest_framework import viewsets

from apps.accounts.filters.organization_profile import OrganizationProfileFilter
from apps.accounts.mixins.views import (
    ModelViewSetMixin,
    OrganizationScopedViewSetMixin,
)
from apps.accounts.models.organization import OrganizationProfile
from apps.accounts.permissions.generics import IsActiveMember
from apps.accounts.permissions.organization_profile import OrganizationProfilePermission
from apps.accounts.serializers.organization_profile import OrganizationProfileSerializer
from apps.generics.utils.schema import extend_schema_model_view_set


@extend_schema_model_view_set(model=OrganizationProfile)
class OrganizationProfileViewSet(
    OrganizationScopedViewSetMixin,
    ModelViewSetMixin,
    viewsets.ModelViewSet,
):
    serializer_class = OrganizationProfileSerializer
    queryset = OrganizationProfile.objects.filter_actives()
    http_method_names = ['get', 'put', 'patch', 'delete', 'options']
    permission_classes = [IsActiveMember, OrganizationProfilePermission]
    filterset_class = OrganizationProfileFilter
    filter_backends = [backends.DjangoFilterBackend]
    label_expression = 'organization__name'
    auto_orderable_filter = True
