from django_filters.rest_framework import backends
from drf_spectacular.utils import extend_schema_view
from rest_framework import viewsets

from apps.accounts.mixins.views import ModelViewSetMixin, OrganizationScopedViewSetMixin
from apps.audit.filters.audit_event import AuditEventFilter
from apps.audit.models.audit_event import AuditEvent
from apps.audit.permissions.audit_event import AuditEventPermission
from apps.audit.serializers.audit_event import AuditEventSerializer
from apps.generics.utils.schema import extend_schema_list, extend_schema_retrieve


@extend_schema_view(
    list=extend_schema_list(model=AuditEvent),
    retrieve=extend_schema_retrieve(model=AuditEvent),
)
class AuditEventViewSet(
    OrganizationScopedViewSetMixin, ModelViewSetMixin, viewsets.ModelViewSet
):
    queryset = AuditEvent.objects.all()
    serializer_class = AuditEventSerializer
    permission_classes = [AuditEventPermission]
    filterset_class = AuditEventFilter
    filter_backends = [backends.DjangoFilterBackend]
    http_method_names = ['get', 'options']
    options_actions = ('list',)
