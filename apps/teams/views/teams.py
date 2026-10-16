from django_filters.rest_framework import backends
from rest_framework import viewsets

from apps.accounts.mixins.views import ModelViewSetMixin, OrganizationScopedViewSetMixin
from apps.audit.choices import AuditActionChoices
from apps.generics.utils.schema import extend_schema_model_view_set
from apps.teams.filters.team import TeamFilter
from apps.teams.models.team import Team
from apps.teams.permissions.team import TeamPermission
from apps.teams.serializers.team import TeamListSerializer, TeamSerializer


@extend_schema_model_view_set(model=Team)
class TeamViewSet(
    OrganizationScopedViewSetMixin, ModelViewSetMixin, viewsets.ModelViewSet
):
    serializer_class = TeamSerializer
    queryset = Team.objects.all()
    http_method_names = ['get', 'post', 'put', 'delete']
    audit_actions = {
        'create': AuditActionChoices.TEAM_CREATED,
        'update': AuditActionChoices.TEAM_UPDATED,
        'destroy': AuditActionChoices.TEAM_DELETED,
    }
    permission_classes = [TeamPermission]
    filterset_class = TeamFilter
    filter_backends = [backends.DjangoFilterBackend]
    base_filters = {'is_active': True}
    auto_orderable_filter = True

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list':
            qs = qs.annotate(member_count=Team.member_count_expression()).order_by(
                '-id'
            )
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return TeamListSerializer
        return super().get_serializer_class()
