from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.audit.models.audit_event import AuditEvent
from apps.platform.filters import (
    PlatformAuditEventFilter,
    PlatformMemberFilter,
    PlatformOrganizationFilter,
    PlatformUserFilter,
)
from apps.platform.permissions import IsPlatformStaff
from apps.platform.selectors import (
    organization_detail_queryset,
    organizations_queryset,
    overview,
    users_queryset,
)
from apps.platform.serializers import (
    PlatformAuditEventSerializer,
    PlatformInvitationSerializer,
    PlatformMemberSerializer,
    PlatformOrganizationDetailSerializer,
    PlatformOrganizationListSerializer,
    PlatformOverviewSerializer,
    PlatformTeamSerializer,
    PlatformUserDetailSerializer,
    PlatformUserListSerializer,
)
from apps.teams.models.team import Team

PLATFORM_TAGS = [_('Platform')]
MEMBER_PARAMETERS = [
    OpenApiParameter('search', OpenApiTypes.STR),
    OpenApiParameter('is_active', OpenApiTypes.BOOL),
    OpenApiParameter('exclude_owner', OpenApiTypes.BOOL),
]


@extend_schema(
    tags=PLATFORM_TAGS,
    description=_('Platform numbers, computed when requested (platform staff).'),
    responses={200: PlatformOverviewSerializer},
)
class PlatformOverviewView(APIView):
    permission_classes = [IsPlatformStaff]
    http_method_names = ['get', 'options']

    def get(self, request, *args, **kwargs):
        serializer = PlatformOverviewSerializer(instance=overview(now=timezone.now()))
        return Response(data=serializer.data, status=status.HTTP_200_OK)


class PlatformReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsPlatformStaff]
    filter_backends = [DjangoFilterBackend]

    def paginated(self, queryset, serializer_class, filterset_class=None):
        if filterset_class is not None:
            filterset = filterset_class(
                self.request.query_params, queryset=queryset, request=self.request
            )
            filterset.is_valid()
            queryset = filterset.qs
        page = self.paginate_queryset(queryset)
        serializer = serializer_class(
            page, many=True, context=self.get_serializer_context()
        )
        return self.get_paginated_response(serializer.data)


@extend_schema_view(
    list=extend_schema(tags=PLATFORM_TAGS),
    retrieve=extend_schema(tags=PLATFORM_TAGS),
    members=extend_schema(
        tags=PLATFORM_TAGS,
        parameters=MEMBER_PARAMETERS,
        responses=PlatformMemberSerializer(many=True),
    ),
    teams=extend_schema(
        tags=PLATFORM_TAGS, responses=PlatformTeamSerializer(many=True)
    ),
    invitations=extend_schema(
        tags=PLATFORM_TAGS, responses=PlatformInvitationSerializer(many=True)
    ),
)
class PlatformOrganizationViewSet(PlatformReadOnlyViewSet):
    filterset_class = PlatformOrganizationFilter

    def get_queryset(self):
        if self.action == 'list':
            return organizations_queryset()
        return organization_detail_queryset()

    def get_serializer_class(self):
        if self.action == 'list':
            return PlatformOrganizationListSerializer
        return PlatformOrganizationDetailSerializer

    def filter_queryset(self, queryset):
        if self.action != 'list':
            return queryset
        return super().filter_queryset(queryset)

    @action(detail=True, methods=['get'])
    def members(self, request, *args, **kwargs):
        organization = self.get_object()
        queryset = (
            Member.objects.filter(organization=organization)
            .select_related('user')
            .order_by('user__full_name', 'id')
        )
        return self.paginated(queryset, PlatformMemberSerializer, PlatformMemberFilter)

    @action(detail=True, methods=['get'])
    def teams(self, request, *args, **kwargs):
        organization = self.get_object()
        queryset = (
            Team.objects.filter(organization=organization, is_active=True)
            .annotate(members_count=Team.member_count_expression())
            .order_by('name', 'id')
        )
        return self.paginated(queryset, PlatformTeamSerializer)

    @action(detail=True, methods=['get'])
    def invitations(self, request, *args, **kwargs):
        organization = self.get_object()
        queryset = (
            Invitation.objects.filter(organization=organization, is_active=True)
            .filter_pending()
            .order_by('expired_at', 'id')
        )
        return self.paginated(queryset, PlatformInvitationSerializer)


@extend_schema_view(
    list=extend_schema(tags=PLATFORM_TAGS),
    retrieve=extend_schema(tags=PLATFORM_TAGS),
)
class PlatformUserViewSet(PlatformReadOnlyViewSet):
    filterset_class = PlatformUserFilter

    def get_queryset(self):
        return users_queryset().select_related('blocked_by')

    def get_serializer_class(self):
        if self.action == 'list':
            return PlatformUserListSerializer
        return PlatformUserDetailSerializer

    def filter_queryset(self, queryset):
        if self.action != 'list':
            return queryset
        return super().filter_queryset(queryset)


@extend_schema_view(
    list=extend_schema(tags=PLATFORM_TAGS),
    retrieve=extend_schema(tags=PLATFORM_TAGS),
)
class PlatformAuditEventViewSet(PlatformReadOnlyViewSet):
    queryset = AuditEvent.objects.select_related('organization', 'impersonator')
    serializer_class = PlatformAuditEventSerializer
    filterset_class = PlatformAuditEventFilter
