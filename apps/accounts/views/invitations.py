from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import backends
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.choices import (
    InvitationEmailErrorMessages,
    InvitationErrorMessages,
    MemberRoleChoices,
)
from apps.accounts.consts import INVITATION_EMAIL_COOLDOWN_SECONDS
from apps.accounts.filters.invitation import InvitationFilter
from apps.accounts.mixins.views import ModelViewSetMixin, OrganizationScopedViewSetMixin
from apps.accounts.models.invitation import Invitation
from apps.accounts.permissions.invitation import InvitationPermission
from apps.accounts.serializers.invitation import InvitationSerializer
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

    def get_queryset(self):
        queryset = super().get_queryset()
        if not (auth_member := self.auth_member):
            return queryset.none()
        role_list = []
        if auth_member.has_manager_permission:
            role_list.extend([MemberRoleChoices.MANAGER, MemberRoleChoices.MEMBER])
        if auth_member.has_admin_permission:
            role_list.append(MemberRoleChoices.ADMIN)
        if auth_member.has_owner_permission:
            role_list.append(MemberRoleChoices.OWNER)
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
        invitation.save(update_fields=['last_email_sent_at'])

        return Response(
            data={'detail': InvitationEmailErrorMessages.SENT_SUCCESS.label},
            status=status.HTTP_200_OK,
        )
