from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import backends
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status as http_status
from rest_framework import viewsets

from apps.accounts.mixins.views import ModelViewSetMixin, OrganizationScopedViewSetMixin
from apps.generics.utils.models import get_verbose_name
from apps.generics.utils.schema import extend_schema_model_view_set
from apps.teams.filters.team_member import TeamMemberFilter
from apps.teams.models.team_member import TeamMember
from apps.teams.permissions.team_member import TeamMemberPermission
from apps.teams.serializers.team_member import (
    TeamMemberSerializer,
    TeamMemberUpdateSerializer,
)


@extend_schema_model_view_set(
    model=TeamMember,
    update=extend_schema(
        tags=TeamMember.schema_tags(),
        description=_('Update a %(name)s.' % {'name': get_verbose_name(TeamMember)}),
        request=TeamMemberUpdateSerializer,
        responses={
            http_status.HTTP_200_OK: TeamMemberUpdateSerializer,
            http_status.HTTP_400_BAD_REQUEST: OpenApiTypes.NONE,
        },
    ),
)
class TeamMemberViewSet(
    OrganizationScopedViewSetMixin, ModelViewSetMixin, viewsets.ModelViewSet
):
    serializer_class = TeamMemberSerializer
    queryset = TeamMember.objects.all()
    http_method_names = ['get', 'post', 'put', 'delete', 'options']
    permission_classes = [TeamMemberPermission]
    filterset_class = TeamMemberFilter
    filter_backends = [backends.DjangoFilterBackend]
    label_expression = TeamMember.label_expression()

    organization_filter = 'team__organization_id'
    base_filters = {
        'is_active': True,
        'team__is_active': True,
        'member__is_active': True,
    }

    def get_serializer_class(self):
        """Get the serializer class for the view."""
        if self.action in ['update', 'partial_update']:
            return TeamMemberUpdateSerializer
        return super().get_serializer_class()
