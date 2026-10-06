from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import backends
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, viewsets
from rest_framework import status as http_status

from apps.accounts.mixins.views import ModelViewSetMixin, OrganizationScopedViewSetMixin
from apps.generics.utils.models import get_verbose_name
from apps.generics.utils.schema import extend_schema_model_view_set
from apps.teams.filters.team_member import TeamMemberFilter
from apps.teams.models.team_member import TeamMember
from apps.teams.permissions.team_member import TeamMemberPermission
from apps.teams.serializers.options import TEAM_ID_PARAM
from apps.teams.serializers.team_member import (
    LAST_OWNER_MESSAGE,
    TeamMemberSerializer,
    TeamMemberUpdateSerializer,
)


@extend_schema_model_view_set(
    model=TeamMember,
    update=extend_schema(
        tags=TeamMember.schema_tags(),
        description=format_lazy(
            _('Update a {name}.'), name=get_verbose_name(TeamMember)
        ),
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
    http_method_names = ['get', 'post', 'put', 'delete']
    permission_classes = [TeamMemberPermission]
    filterset_class = TeamMemberFilter
    filter_backends = [backends.DjangoFilterBackend]
    auto_orderable_filter = True
    options_form_parameters = (
        OpenApiParameter(
            name=TEAM_ID_PARAM,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=False,
            description=_(
                'Team the form is for: `role` lists only the roles the caller may '
                'assign in it and `member` hides members already in it. Without a '
                'valid team only organization managers get roles.'
            ),
        ),
    )

    organization_filter = 'team__organization_id'
    base_filters = {
        'is_active': True,
        'team__is_active': True,
        'member__is_active': True,
    }

    def get_queryset(self):
        return super().get_queryset().select_related('team', 'member__user')

    def perform_destroy(self, instance):
        if instance.is_last_owner:
            raise serializers.ValidationError({'role': [LAST_OWNER_MESSAGE]})
        super().perform_destroy(instance)

    def get_serializer_class(self):
        """Get the serializer class for the view."""
        if self.action in ['update', 'partial_update']:
            return TeamMemberUpdateSerializer
        return super().get_serializer_class()
