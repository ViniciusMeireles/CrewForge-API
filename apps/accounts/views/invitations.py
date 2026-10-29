from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
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
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.choices import (
    InvitationEmailErrorMessages,
    InvitationErrorMessages,
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
from apps.accounts.tokens import VersionedRefreshToken
from apps.accounts.utils.auth_cookies import move_tokens_to_cookies
from apps.accounts.utils.security_log import log_security_event
from apps.audit.choices import AuditActionChoices
from apps.audit.services import record_audit_event
from apps.generics.decorators import action_custom
from apps.generics.utils.schema import extend_schema_model_view_set


@extend_schema_model_view_set(
    model=Invitation,
    send_email=extend_schema(
        request=OpenApiTypes.NONE,
        tags=Invitation.schema_tags(),
        summary=_('Send invitation email'),
        description=_(
            'Email the invitation to its recipient again. A cooldown applies between '
            'sends.'
        ),
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=inline_serializer(
                    name='SendInviteEmailSuccess',
                    fields={'detail': serializers.CharField()},
                ),
                examples=[
                    OpenApiExample(
                        name=InvitationEmailErrorMessages.SENT_SUCCESS.label,
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
                        name=InvitationErrorMessages.INVITATION_EXPIRED.label,
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_EXPIRED.label
                            )
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name=InvitationErrorMessages.USER_ALREADY_MEMBER.label,
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
                        name=InvitationEmailErrorMessages.COOLDOWN_ACTIVE.label,
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
        summary=_('List received invitations'),
        description=_(
            'Paginated list of the invitations addressed to the authenticated user, '
            'from any organization.'
        ),
        responses={
            status.HTTP_200_OK: InvitationReceivedSerializer(many=True),
        },
    ),
    received_detail=extend_schema(
        tags=Invitation.schema_tags(),
        summary=_('Get received invitation'),
        description=_('Return an invitation addressed to the authenticated user.'),
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
        summary=_('Get invitation by key'),
        description=_(
            'Return the invitation identified by the secret key of its invitation link.'
        ),
        responses={
            status.HTTP_200_OK: InvitationByKeySerializer,
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                response=inline_serializer(
                    name='ByKeyNotFound',
                    fields={'detail': serializers.CharField()},
                ),
                examples=[
                    OpenApiExample(
                        name=InvitationErrorMessages.INVITATION_NOT_FOUND.label,
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
        summary=_('Accept invitation'),
        description=_(
            'Accept an invitation and create a member record, or reactivate the '
            'removed member of the user (readmission).'
        ),
        responses={
            status.HTTP_200_OK: inline_serializer(
                name='InvitationAcceptSuccess',
                fields={
                    'access': serializers.CharField(),
                    'refresh': serializers.CharField(),
                    'member_id': serializers.IntegerField(),
                    'readmitted': serializers.BooleanField(),
                },
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                response=inline_serializer(
                    name='InvitationAcceptBadRequest',
                    fields={'detail': serializers.CharField()},
                ),
                examples=[
                    OpenApiExample(
                        name=InvitationErrorMessages.INVITATION_ACCEPTED.label,
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_ACCEPTED.label
                            )
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name=InvitationErrorMessages.INVITATION_DECLINED.label,
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_DECLINED.label
                            )
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name=InvitationErrorMessages.INVITATION_EXPIRED.label,
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_EXPIRED.label
                            )
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name=InvitationErrorMessages.USER_ALREADY_MEMBER.label,
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
                        name=InvitationErrorMessages.INVITATION_NOT_FOUND.label,
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
        summary=_('Decline invitation'),
        description=_(
            'Decline a pending invitation addressed to the authenticated user.'
        ),
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
                        name=InvitationErrorMessages.INVITATION_ACCEPTED.label,
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_ACCEPTED.label
                            )
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name=InvitationErrorMessages.INVITATION_DECLINED.label,
                        value={
                            'detail': str(
                                InvitationErrorMessages.INVITATION_DECLINED.label
                            )
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        name=InvitationErrorMessages.INVITATION_EXPIRED.label,
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
                        name=InvitationErrorMessages.INVITATION_NOT_FOUND.label,
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
    http_method_names = ['get', 'post', 'put', 'delete']
    audit_actions = {
        'create': AuditActionChoices.INVITATION_CREATED,
        'update': AuditActionChoices.INVITATION_UPDATED,
        'destroy': AuditActionChoices.INVITATION_DELETED,
    }
    audit_exclude_fields = ('key', 'last_email_sent_at')
    permission_classes = [InvitationPermission]
    organization_context_exempt_actions = (
        'received',
        'received_detail',
        'by_key',
        'accept',
        'decline',
    )
    filterset_class = InvitationFilter
    filter_backends = [backends.DjangoFilterBackend]
    auto_orderable_filter = True
    options_actions = ('create', 'update', 'list', 'received')
    options_schema = {
        'received': {
            'summary': _('Received invitations filter options'),
            'description': _(
                'Return the choices of each filter of the received invitations list. '
                'Send a field name as query parameter to get only that field.'
            ),
        },
    }

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter_visible_to(self.auth_member)
            .annotate_former_member()
        )

    def record_acceptance(self, invitation, member, readmitted: bool) -> None:
        """
        Log the acceptance as before (``member.readmitted`` or
        ``invitation.accepted``) and audit both the Invitation and the Member.
        """
        logged, audited = (
            (
                AuditActionChoices.MEMBER_READMITTED,
                AuditActionChoices.INVITATION_ACCEPTED,
            )
            if readmitted
            else (
                AuditActionChoices.INVITATION_ACCEPTED,
                AuditActionChoices.MEMBER_JOINED,
            )
        )
        targets = {
            AuditActionChoices.INVITATION_ACCEPTED: {'target': invitation},
            AuditActionChoices.MEMBER_READMITTED: self.member_audit(member),
            AuditActionChoices.MEMBER_JOINED: self.member_audit(member),
        }
        log_security_event(
            logged,
            self.request,
            invitation_id=invitation.pk,
            organization_id=invitation.organization_id,
            member_id=member.pk,
            audit={'actor_member': member, **targets[logged]},
        )
        record_audit_event(
            audited,
            request=self.request,
            organization_id=invitation.organization_id,
            actor_member=member,
            metadata={'invitation_id': invitation.pk, 'member_id': member.pk},
            **targets[audited],
        )

    @staticmethod
    def member_audit(member) -> dict:
        return {
            'target': member,
            'changes': [{'field': 'role', 'before': None, 'after': member.role}],
        }

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

        with transaction.atomic():
            transaction.on_commit(invitation.send_email)
            invitation.last_email_sent_at = timezone.now()
            invitation.save(update_fields=['last_email_sent_at', 'updated_at'])
            record_audit_event(
                AuditActionChoices.INVITATION_EMAIL_SENT,
                request=request,
                target=invitation,
            )

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
        if self.auth_user and self.auth_user.email_verified:
            queryset = Invitation.objects.filter_actives().filter_received_by_user(
                user=self.auth_user,
            )
        else:
            queryset = Invitation.objects.filter_pending()
        invitation = get_object_or_404(
            queryset,
            key=kwargs.get('invitation_key'),
        )
        serializer = self.get_serializer(invitation)
        return Response(data=serializer.data)

    def _locked_invitation(self, request, kwargs) -> Invitation:
        invitation = get_object_or_404(
            Invitation.objects.select_for_update(of=('self',)).filter_actives(),
            pk=kwargs.get('invitation_pk'),
        )
        self.check_object_permissions(request, invitation)
        return invitation

    @action(
        detail=False,
        methods=['post'],
        url_path=r'(?P<invitation_pk>\d+)/accept',
        permission_classes=[InvitationAcceptDeclinePermission],
        serializer_class=InvitationAcceptSerializer,
    )
    def accept(self, request, *args, **kwargs):
        from apps.accounts.models.member import Member

        accept_serializer = InvitationAcceptSerializer(data=request.data)
        accept_serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                invitation = self._locked_invitation(request, kwargs)
                invitation.ensure_organization_not_suspended()
                is_acceptable, message = invitation.is_acceptable()
                if not is_acceptable:
                    raise ValueError(message)
                member, readmitted = Member.objects.admit(
                    user=request.user,
                    organization=invitation.organization,
                    role=invitation.role,
                    nickname=accept_serializer.validated_data.get('nickname', ''),
                )
                invitation.accept(member=member, check=False)
                self.record_acceptance(invitation, member, readmitted)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        except ValueError as exc:
            return Response(
                data={'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = VersionedRefreshToken.for_user(request.user)
        response = Response(
            data={
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'member_id': member.id,
                'readmitted': readmitted,
            }
        )
        return move_tokens_to_cookies(request, response, response.data)

    @action(
        detail=False,
        methods=['post'],
        url_path=r'(?P<invitation_pk>\d+)/decline',
        permission_classes=[InvitationAcceptDeclinePermission],
    )
    def decline(self, request, *args, **kwargs):
        with transaction.atomic():
            invitation = self._locked_invitation(request, kwargs)
            is_declinable, message = invitation.is_declinable()
            if not is_declinable:
                return Response(
                    data={'detail': message},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            invitation.decline(user=self.auth_user, check=False)
            record_audit_event(
                AuditActionChoices.INVITATION_DECLINED,
                request=request,
                organization_id=invitation.organization_id,
                target=invitation,
            )
        return Response(data={'detail': _('Invitation declined successfully.')})
