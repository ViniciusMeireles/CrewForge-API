from django_filters.rest_framework import backends
from rest_framework import viewsets

from apps.accounts.filters.invitation import InvitationFilter
from apps.accounts.mixins.views import ModelViewSetMixin, OrganizationScopedViewSetMixin
from apps.accounts.models.invitation import Invitation
from apps.accounts.permissions.invitation import InvitationPermission
from apps.accounts.serializers.invitation import InvitationSerializer
from apps.generics.utils.schema import extend_schema_model_view_set


@extend_schema_model_view_set(model=Invitation)
class InvitationViewSet(
    OrganizationScopedViewSetMixin, ModelViewSetMixin, viewsets.ModelViewSet
):
    serializer_class = InvitationSerializer
    queryset = Invitation.objects.filter(is_active=True)
    http_method_names = ['get', 'post', 'put', 'delete', 'options']
    permission_classes = [InvitationPermission]
    lookup_field = 'key'
    filterset_class = InvitationFilter
    filter_backends = [backends.DjangoFilterBackend]
    label_expression = 'email'
