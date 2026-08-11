from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import backends
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.choices import (
    InvitationEmailErrorMessages,
    InvitationErrorMessages,
    MemberRoleChoices,
)
from apps.accounts.consts import INVITATION_EMAIL_COOLDOWN_SECONDS
from apps.accounts.filters.invitation import (
    InvitationAcceptanceFilter,
    InvitationFilter,
)
from apps.accounts.mixins.views import ModelViewSetMixin, OrganizationScopedViewSetMixin
from apps.accounts.models.invitation import Invitation
from apps.accounts.permissions.invitation import (
    InvitationAcceptDeclinePermission,
    InvitationPermission,
)
from apps.accounts.serializers.invitation import (
    InvitationAcceptSerializer,
    InvitationByKeySerializer,
    InvitationReceivedDetailSerializer,
    InvitationReceivedSerializer,
    InvitationSerializer,
)
from apps.generics.decorators import action_custom
from apps.generics.utils.schema import extend_schema_model_view_set


@extend_schema_model_view_set(
    model=Invitation,
    send_email=extend_schema(
        request=OpenApiTypes.NONE,
        tags=Invitation.schema_tags(),
        description=_('Send an invitation email.'),
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=inline_serializer(
                    name='SendInviteEmailSuccess',
                    fields={'detail': serializers.CharField()},
                ),
                examples=[
                    OpenApiExample(
                        name=str(InvitationEmailErrorMessages.SENT_SUCCESS.label),
                        value={
                            'detail': str(
                                InvitationEmailErrorMessages.SENT_SUCCESS.label
                            ),
                        },
                        response_only=True,
                    ),
                ],
                description=_('The invitation email has been sent successfully.'),
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                response=inline_serializer(
                    name='SendInviteEmailBadRequest',
                    fields={'detail': serializers.CharField()},
                ),
                examples=[
                    OpenApiExample(
                        name=str(InvitationErrorMessages.INVITATION_EXPIRED.label),
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_EXPIRED.label
                            )
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name=str(InvitationErrorMessages.USER_ALREADY_MEMBER.label),
                        value={
                            'detail': str(
                                InvitationErrorMessages.USER_ALREADY_MEMBER.label
                            )
                        },
                        response_only=True,
                    ),
                ],
                description=_(
                    'The invitation is expired or the user is already a member.'
                ),
            ),
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                response=inline_serializer(
                    name='SendInviteEmailTooManyRequests',
                    fields={
                        'detail': serializers.CharField(),
                        'code': serializers.CharField(),
                        'retry_after_seconds': serializers.IntegerField(),
                    },
                ),
                examples=[
                    OpenApiExample(
                        name=str(InvitationEmailErrorMessages.COOLDOWN_ACTIVE.label),
                        value={
                            'detail': str(
                                InvitationEmailErrorMessages.COOLDOWN_ACTIVE.label,
                            ),
                            'code': str(
                                InvitationEmailErrorMessages.COOLDOWN_ACTIVE.value,
                            ),
                            'retry_after_seconds': INVITATION_EMAIL_COOLDOWN_SECONDS,
                        },
                        response_only=True,
                    ),
                ],
                description=_('The invitation email cooldown is active.'),
            ),
        },
    ),
    received=extend_schema(
        tags=Invitation.schema_tags(),
        description=_('List received invitations for the authenticated user.'),
        responses={
            status.HTTP_200_OK: InvitationReceivedSerializer(many=True),
        },
    ),
    received_detail=extend_schema(
        tags=Invitation.schema_tags(),
        description=_('Retrieve a received invitation detail.'),
        responses={
            status.HTTP_200_OK: InvitationReceivedDetailSerializer,
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                response=inline_serializer(
                    name='ReceivedDetailNotFound',
                    fields={'detail': serializers.CharField()},
                ),
                description=_('Invitation not found.'),
            ),
        },
    ),
    by_key=extend_schema(
        parameters=[
            OpenApiParameter(
                name='invitation_key',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description=_('The secret key of the invitation.'),
                required=True,
            ),
        ],
        tags=Invitation.schema_tags(),
        description=_('Retrieve an invitation by its secret key.'),
        responses={
            status.HTTP_200_OK: InvitationByKeySerializer,
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                response=inline_serializer(
                    name='ByKeyNotFound',
                    fields={'detail': serializers.CharField()},
                ),
                examples=[
                    OpenApiExample(
                        name=str(InvitationErrorMessages.INVITATION_NOT_FOUND.label),
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_NOT_FOUND.label
                            )
                        },
                        response_only=True,
                    ),
                ],
                description=_('Invitation not found.'),
            ),
        },
    ),
    accept=extend_schema(
        request=InvitationAcceptSerializer,
        tags=Invitation.schema_tags(),
        description=_('Accept an invitation and create a member record.'),
        responses={
            status.HTTP_200_OK: inline_serializer(
                name='InvitationAcceptSuccess',
                fields={
                    'access': serializers.CharField(),
                    'refresh': serializers.CharField(),
                    'member_id': serializers.IntegerField(),
                },
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                response=inline_serializer(
                    name='InvitationAcceptBadRequest',
                    fields={'detail': serializers.CharField()},
                ),
                examples=[
                    OpenApiExample(
                        name=str(InvitationErrorMessages.INVITATION_ACCEPTED.label),
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_ACCEPTED.label
                            )
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name=str(InvitationErrorMessages.INVITATION_DECLINED.label),
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_DECLINED.label
                            )
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name=str(InvitationErrorMessages.INVITATION_EXPIRED.label),
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_EXPIRED.label
                            )
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name=str(InvitationErrorMessages.USER_ALREADY_MEMBER.label),
                        value={
                            'detail': str(
                                InvitationErrorMessages.USER_ALREADY_MEMBER.label
                            )
                        },
                        response_only=True,
                    ),
                ],
                description=_('The invitation is no longer acceptable.'),
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                response=inline_serializer(
                    name='InvitationAcceptNotFound',
                    fields={'detail': serializers.CharField()},
                ),
                examples=[
                    OpenApiExample(
                        name=str(InvitationErrorMessages.INVITATION_NOT_FOUND.label),
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_NOT_FOUND.label
                            )
                        },
                        response_only=True,
                    ),
                ],
                description=_('Invitation not found.'),
            ),
        },
    ),
    decline=extend_schema(
        request=OpenApiTypes.NONE,
        tags=Invitation.schema_tags(),
        description=_('Decline an invitation.'),
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=inline_serializer(
                    name='InvitationDeclineSuccess',
                    fields={'detail': serializers.CharField()},
                ),
                examples=[
                    OpenApiExample(
                        name='Decline success',
                        value={'detail': 'Invitation declined successfully.'},
                        response_only=True,
                    ),
                ],
                description=_('The invitation has been declined successfully.'),
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                response=inline_serializer(
                    name='InvitationDeclineBadRequest',
                    fields={'detail': serializers.CharField()},
                ),
                examples=[
                    OpenApiExample(
                        name=str(InvitationErrorMessages.INVITATION_ACCEPTED.label),
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_ACCEPTED.label
                            )
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name=str(InvitationErrorMessages.INVITATION_DECLINED.label),
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_DECLINED.label
                            )
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name=str(InvitationErrorMessages.INVITATION_EXPIRED.label),
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_EXPIRED.label
                            )
                        },
                        response_only=True,
                    ),
                ],
                description=_('The invitation is not in a pending state.'),
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                response=inline_serializer(
                    name='InvitationDeclineNotFound',
                    fields={'detail': serializers.CharField()},
                ),
                examples=[
                    OpenApiExample(
                        name=str(InvitationErrorMessages.INVITATION_NOT_FOUND.label),
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_NOT_FOUND.label
                            )
                        },
                        response_only=True,
                    ),
                ],
                description=_('Invitation not found.'),
            ),
        },
    ),
)
class InvitationViewSet(
    OrganizationScopedViewSetMixin, ModelViewSetMixin, viewsets.ModelViewSet
):
    serializer_class = InvitationSerializer
    queryset = Invitation.objects.filter(is_active=True)
    http_method_names = ['get', 'post', 'put', 'delete', 'options']
    permission_classes = [InvitationPermission]
    filterset_class = InvitationFilter
    filter_backends = [backends.DjangoFilterBackend]
    label_expression = 'email'
    auto_orderable_filter = True

    def get_queryset(self):
        queryset = super().get_queryset()
        if not (auth_member := self.auth_member):
            return queryset.none()
        role_list = []
        if auth_member.has_admin_permission:
            role_list.extend([MemberRoleChoices.MANAGER, MemberRoleChoices.MEMBER])
        if auth_member.has_owner_permission:
            role_list.extend([MemberRoleChoices.OWNER, MemberRoleChoices.ADMIN])
        queryset = queryset.filter(role__in=role_list)
        return queryset

    @action(detail=True, methods=['post'], url_path='send-email')
    def send_email(self, request, *args, **kwargs):
        invitation = self.get_object()

        is_acceptable, message = invitation.is_acceptable()
        if not is_acceptable:
            return Response(
                data={'detail': message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if invitation.last_email_sent_at:
            elapsed = (timezone.now() - invitation.last_email_sent_at).total_seconds()
            if elapsed < INVITATION_EMAIL_COOLDOWN_SECONDS:
                retry_after = int(INVITATION_EMAIL_COOLDOWN_SECONDS - elapsed)
                return Response(
                    data={
                        'detail': InvitationEmailErrorMessages.COOLDOWN_ACTIVE.label,
                        'code': InvitationEmailErrorMessages.COOLDOWN_ACTIVE.value,
                        'retry_after_seconds': retry_after,
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        invitation.send_email()

        invitation.last_email_sent_at = timezone.now()
        invitation.save(update_fields=['last_email_sent_at', 'updated_at'])

        return Response(
            data={'detail': InvitationEmailErrorMessages.SENT_SUCCESS.label},
            status=status.HTTP_200_OK,
        )

    @action_custom(
        detail=False,
        methods=['get'],
        url_path='received',
        permission_classes=[IsAuthenticated],
        serializer_class=InvitationReceivedSerializer,
        filterset_class=InvitationAcceptanceFilter,
        auto_orderable_filter=True,
    )
    def received(self, request, *args, **kwargs):
        queryset = Invitation.objects.filter_actives().filter_received_by_user(
            user=self.auth_user,
        )
        queryset = self.filter_queryset(queryset)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(data=serializer.data)

    @action(
        detail=False,
        methods=['get'],
        url_path=r'received/(?P<invitation_pk>\d+)',
        permission_classes=[IsAuthenticated],
        serializer_class=InvitationReceivedDetailSerializer,
    )
    def received_detail(self, request, *args, **kwargs):
        invitation = get_object_or_404(
            Invitation.objects.filter_actives().filter_received_by_user(
                user=self.auth_user,
            ),
            pk=kwargs.get('invitation_pk'),
        )
        serializer = self.get_serializer(invitation)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['get'],
        url_path=r'by-key/(?P<invitation_key>[^/.]+)',
        permission_classes=[AllowAny],
        serializer_class=InvitationByKeySerializer,
    )
    def by_key(self, request, *args, **kwargs):
        if self.auth_user:
            queryset = Invitation.objects.filter_actives().filter_received_by_user(
                user=self.auth_user,
            )
        else:
            queryset = Invitation.objects.filter_acceptable()
        invitation = get_object_or_404(
            queryset,
            key=kwargs.get('invitation_key'),
        )
        serializer = self.get_serializer(invitation)
        return Response(data=serializer.data)

    @action(
        detail=False,
        methods=['post'],
        url_path=r'(?P<invitation_pk>\d+)/accept',
        permission_classes=[InvitationAcceptDeclinePermission],
        serializer_class=InvitationAcceptSerializer,
    )
    def accept(self, request, *args, **kwargs):
        invitation_pk = kwargs.get('invitation_pk')
        invitation = get_object_or_404(Invitation, pk=invitation_pk)
        self.check_object_permissions(request, invitation)

        is_acceptable, message = invitation.is_acceptable()
        if not is_acceptable:
            return Response(
                data={'detail': message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.accounts.models.member import Member

        nickname = request.data.get('nickname', '')
        member = Member.objects.create(
            user=request.user,
            organization=invitation.organization,
            role=invitation.role,
            nickname=nickname if nickname else None,
        )
        invitation.accept(member=member, check=False)

        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(request.user)
        return Response(
            data={
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'member_id': member.id,
            }
        )

    @action(
        detail=False,
        methods=['post'],
        url_path=r'(?P<invitation_pk>\d+)/decline',
        permission_classes=[InvitationAcceptDeclinePermission],
    )
    def decline(self, request, *args, **kwargs):
        invitation_pk = kwargs.get('invitation_pk')
        invitation = get_object_or_404(Invitation, pk=invitation_pk)
        self.check_object_permissions(request, invitation)

        is_declinable, message = invitation.is_declinable()
        if not is_declinable:
            return Response(
                data={'detail': message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation.decline(user=self.auth_user, check=False)
        return Response(data={'detail': _('Invitation declined successfully.')})
