from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import backends
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.filters.members import MemberFilter
from apps.accounts.mixins.views import ModelViewSetMixin, OrganizationScopedViewSetMixin
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.accounts.permissions.member import MemberPermission
from apps.accounts.serializers.member import (
    MemberModelSerializer,
    MemberRoleUpdateSerializer,
    MemberUpdateSerializer,
    MemberWithInviteCreateSerializer,
)
from apps.generics.utils.models import get_verbose_name
from apps.generics.utils.schema import extend_schema_model_view_set


@extend_schema_model_view_set(
    model=Member,
    create_with_invite=extend_schema(
        request=MemberWithInviteCreateSerializer,
        parameters=[
            OpenApiParameter(
                name='invitation_key',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description=_('The secret key of the invitation.'),
                required=True,
            ),
        ],
        tags=Member.schema_tags(),
        description=_(
            'Create a new %(name)s with an invitation.'
            % {'name': get_verbose_name(Member)}
        ),
    ),
    # Create route is excluded
    create=extend_schema(exclude=True),
    update_role=extend_schema(
        request=MemberRoleUpdateSerializer,
        responses={
            http_status.HTTP_200_OK: MemberRoleUpdateSerializer,
            http_status.HTTP_400_BAD_REQUEST: OpenApiTypes.NONE,
        },
        tags=Member.schema_tags(),
        description=_(
            'Update the role of a %(name)s.' % {'name': get_verbose_name(Member)}
        ),
    ),
    update=extend_schema(
        request=MemberUpdateSerializer,
        responses={
            http_status.HTTP_200_OK: MemberUpdateSerializer,
            http_status.HTTP_400_BAD_REQUEST: OpenApiTypes.NONE,
        },
        tags=Member.schema_tags(),
        description=_('Update a %(name)s.' % {'name': get_verbose_name(Member)}),
    ),
)
class MemberViewSet(
    OrganizationScopedViewSetMixin, ModelViewSetMixin, viewsets.ModelViewSet
):
    queryset = Member.objects.all()
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'options']
    permission_classes = [MemberPermission]
    filterset_class = MemberFilter
    filter_backends = [backends.DjangoFilterBackend]
    label_expression = Member.label_expression()

    base_filters = {'is_active': True}

    def get_serializer_class(self):
        """Get the serializer class for the view."""
        if self.action in ['update', 'partial_update']:
            return MemberUpdateSerializer
        elif self.action == 'update_role':
            return MemberRoleUpdateSerializer
        elif self.action == 'create_with_invite':
            return MemberWithInviteCreateSerializer
        return MemberModelSerializer

    def get_invitation(self) -> Invitation | None:
        """Get the invitation object."""
        return (
            Invitation.objects.filter(
                key=self.kwargs.get('invitation_key'),
                is_active=True,
                is_expired=False,
                is_accepted=False,
            )
            .exclude(
                expired_at__lt=timezone.now(),
            )
            .get_or_none()
        )

    def create(self, request, *args, **kwargs):
        """Deprecated create action."""
        return Response(
            data={
                'detail': _(
                    'This route is not available anymore. Use the `create_with_invite` '
                    'route instead.'
                )
            },
            status=http_status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(
        detail=False,
        methods=['post'],
        url_path='create-with-invite/(?P<invitation_key>[^/.]+)',
    )
    def create_with_invite(self, request, *args, **kwargs):
        """Create a new member."""
        if not (invitation := self.get_invitation()):
            return Response(
                data={'detail': _('Invitation not found or expired.')},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        is_acceptable, message = invitation.is_acceptable()
        if not is_acceptable:
            return Response(
                data={'detail': message}, status=http_status.HTTP_400_BAD_REQUEST
            )

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Perform the create action."""
        member = serializer.save()
        if invitation := self.get_invitation():
            invitation.accept(member=member, check=False)

    @action(detail=True, methods=['patch'], url_path='update-role')
    def update_role(self, request, *args, **kwargs):
        """Update the role of a member."""
        kwargs.update({'partial': True})
        return self.update(request, *args, **kwargs)
