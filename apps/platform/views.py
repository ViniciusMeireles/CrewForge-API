from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters import utils as filter_utils
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.audit.models.audit_event import AuditEvent
from apps.generics.mixins.views import OptionsModelMixin
from apps.platform.filters import (
    PlatformAuditEventFilter,
    PlatformMemberFilter,
    PlatformOrganizationFilter,
    PlatformUserFilter,
)
from apps.platform.permissions import IsPlatformAdmin, IsPlatformStaff
from apps.platform.selectors import (
    organization_detail_queryset,
    organizations_queryset,
    overview,
    users_queryset,
)
from apps.platform.serializers import (
    OwnershipTransferSerializer,
    PlatformAuditEventSerializer,
    PlatformInvitationSerializer,
    PlatformMemberSerializer,
    PlatformOrganizationDetailSerializer,
    PlatformOrganizationListSerializer,
    PlatformOverviewSerializer,
    PlatformTeamSerializer,
    PlatformUserDetailSerializer,
    PlatformUserListSerializer,
    ReasonOptionalSerializer,
    ReasonRequiredSerializer,
)
from apps.platform.services import (
    block_user,
    end_sessions,
    force_password_reset,
    reactivate_organization,
    resend_verification,
    suspend_organization,
    transfer_ownership,
    unblock_user,
)
from apps.teams.models.team import Team

PLATFORM_TAGS = [_('Platform')]
TAB_ACTIONS = ('members', 'teams', 'invitations')
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


class PlatformViewSetMixin:
    permission_classes = [IsPlatformStaff]
    filter_backends = [DjangoFilterBackend]

    def paginated(self, queryset, serializer_class, filterset_class=None):
        if filterset_class is not None:
            filterset = filterset_class(
                self.request.query_params, queryset=queryset, request=self.request
            )
            if not filterset.is_valid():
                raise filter_utils.translate_validation(filterset.errors)
            queryset = filterset.qs
        page = self.paginate_queryset(queryset)
        serializer = serializer_class(
            page, many=True, context=self.get_serializer_context()
        )
        return self.get_paginated_response(serializer.data)

    def filter_queryset(self, queryset):
        if self.action != 'list':
            return queryset
        return super().filter_queryset(queryset)

    def get_action_serializer_kwargs(self, instance) -> dict:
        return {}

    def run_action(self, service, request_serializer):
        """Validate the body, run ``service`` on the object, answer with its detail."""
        instance = self.get_object()
        serializer = request_serializer(
            data=self.request.data, **self.get_action_serializer_kwargs(instance)
        )
        serializer.is_valid(raise_exception=True)
        service(self.request, instance, **serializer.validated_data)
        refreshed = self.get_queryset().get(pk=instance.pk)
        return Response(
            data=self.get_serializer_class()(
                refreshed, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )


class PlatformReadOnlyViewSet(PlatformViewSetMixin, viewsets.ModelViewSet):
    http_method_names = ['get', 'head', 'options']


class PlatformActionsViewSet(PlatformViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Reads for staff; ``post`` only reaches the account actions (no ``create``)."""

    http_method_names = ['get', 'head', 'options', 'post']
    action_permission_classes = [IsPlatformAdmin]

    def get_permissions(self):
        if self.action in self.account_actions:
            return [permission() for permission in self.action_permission_classes]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action in self.account_actions:
            return self.detail_serializer_class
        return super().get_serializer_class()


def action_schema(request, response):
    return extend_schema(
        tags=PLATFORM_TAGS,
        request=request,
        responses={200: response},
    )


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
    suspend=action_schema(
        ReasonRequiredSerializer, PlatformOrganizationDetailSerializer
    ),
    reactivate=action_schema(
        ReasonOptionalSerializer, PlatformOrganizationDetailSerializer
    ),
    transfer_ownership=action_schema(
        OwnershipTransferSerializer, PlatformOrganizationDetailSerializer
    ),
)
class PlatformOrganizationViewSet(PlatformActionsViewSet):
    filterset_class = PlatformOrganizationFilter
    account_actions = ('suspend', 'reactivate', 'transfer_ownership')
    detail_serializer_class = PlatformOrganizationDetailSerializer

    def get_queryset(self):
        if self.action == 'list':
            return organizations_queryset()
        if self.action in TAB_ACTIONS:
            return Organization.objects.all()
        return organization_detail_queryset()

    @action(detail=True, methods=['post'])
    def suspend(self, request, *args, **kwargs):
        return self.run_action(suspend_organization, ReasonRequiredSerializer)

    @action(detail=True, methods=['post'])
    def reactivate(self, request, *args, **kwargs):
        return self.run_action(reactivate_organization, ReasonOptionalSerializer)

    @action(detail=True, methods=['post'], url_path='transfer-ownership')
    def transfer_ownership(self, request, *args, **kwargs):
        return self.run_action(transfer_ownership, OwnershipTransferSerializer)

    def get_action_serializer_kwargs(self, instance) -> dict:
        if self.action == 'transfer_ownership':
            return {'organization': instance}
        return {}

    def get_serializer_class(self):
        if self.action == 'list':
            return PlatformOrganizationListSerializer
        return PlatformOrganizationDetailSerializer

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
    block=action_schema(ReasonRequiredSerializer, PlatformUserDetailSerializer),
    unblock=action_schema(ReasonOptionalSerializer, PlatformUserDetailSerializer),
    end_sessions=action_schema(ReasonOptionalSerializer, PlatformUserDetailSerializer),
    resend_verification=action_schema(
        ReasonOptionalSerializer, PlatformUserDetailSerializer
    ),
    force_password_reset=action_schema(
        ReasonOptionalSerializer, PlatformUserDetailSerializer
    ),
)
class PlatformUserViewSet(PlatformActionsViewSet):
    filterset_class = PlatformUserFilter
    account_actions = (
        'block',
        'unblock',
        'end_sessions',
        'resend_verification',
        'force_password_reset',
    )
    detail_serializer_class = PlatformUserDetailSerializer

    def get_queryset(self):
        return users_queryset().select_related('blocked_by')

    def get_serializer_class(self):
        if self.action == 'list':
            return PlatformUserListSerializer
        return PlatformUserDetailSerializer

    @action(detail=True, methods=['post'])
    def block(self, request, *args, **kwargs):
        return self.run_action(block_user, ReasonRequiredSerializer)

    @action(detail=True, methods=['post'])
    def unblock(self, request, *args, **kwargs):
        return self.run_action(unblock_user, ReasonOptionalSerializer)

    @action(detail=True, methods=['post'], url_path='end-sessions')
    def end_sessions(self, request, *args, **kwargs):
        return self.run_action(end_sessions, ReasonOptionalSerializer)

    @action(detail=True, methods=['post'], url_path='resend-verification')
    def resend_verification(self, request, *args, **kwargs):
        return self.run_action(resend_verification, ReasonOptionalSerializer)

    @action(detail=True, methods=['post'], url_path='force-password-reset')
    def force_password_reset(self, request, *args, **kwargs):
        return self.run_action(force_password_reset, ReasonOptionalSerializer)


@extend_schema_view(
    list=extend_schema(tags=PLATFORM_TAGS),
    retrieve=extend_schema(tags=PLATFORM_TAGS),
    filter_options=extend_schema(tags=PLATFORM_TAGS),
)
class PlatformAuditEventViewSet(OptionsModelMixin, PlatformReadOnlyViewSet):
    """Audit Events of every Organization and account, for platform staff."""

    options_actions = ('list',)
    options_component_prefix = 'Platform'
    queryset = AuditEvent.objects.select_related('organization', 'impersonator')
    serializer_class = PlatformAuditEventSerializer
    filterset_class = PlatformAuditEventFilter
