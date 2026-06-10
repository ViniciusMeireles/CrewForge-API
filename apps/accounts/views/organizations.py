from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import backends
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, viewsets
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.filters.organization import OrganizationFilter
from apps.accounts.mixins.views import ModelViewSetMixin
from apps.accounts.models.organization import Organization
from apps.accounts.permissions.organization import OrganizationPermission
from apps.accounts.serializers.organization import (
    OrganizationListSerializer,
    OrganizationSerializer,
)
from apps.accounts.serializers.session import SessionSerializer
from apps.accounts.utils.requests import get_member
from apps.generics.utils.schema import extend_schema_list, extend_schema_model_view_set


@extend_schema_model_view_set(
    model=Organization,
    login=extend_schema(
        tags=Organization.schema_tags(),
        description=_('Login to the organization.'),
        request=None,
        responses={
            http_status.HTTP_200_OK: SessionSerializer,
            http_status.HTTP_404_NOT_FOUND: OpenApiResponse(
                response=inline_serializer(
                    name='LoginNotFoundResponse',
                    fields={
                        'detail': serializers.CharField(),
                    },
                ),
                examples=[
                    OpenApiExample(
                        name=str(_('Organization not found')),
                        value={'detail': _('Organization not found.')},
                        response_only=True,
                    )
                ],
                description=_('Organization not found.'),
            ),
            http_status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                response=inline_serializer(
                    name='LoginUnauthorizedResponse',
                    fields={
                        'detail': serializers.CharField(),
                    },
                ),
                examples=[
                    OpenApiExample(
                        name=str(_('User not authenticated')),
                        value={'detail': _('User not authenticated.')},
                        response_only=True,
                    )
                ],
                description=_('User not authenticated.'),
            ),
        },
    ),
    list=extend_schema_list(model=Organization, responses=OrganizationListSerializer),
)
class OrganizationViewSet(ModelViewSetMixin, viewsets.ModelViewSet):
    """View for handling organization CRUD operations."""

    serializer_class = OrganizationSerializer
    queryset = Organization.objects.all()
    http_method_names = ['get', 'put', 'post', 'delete', 'options']
    permission_classes = [OrganizationPermission]
    filterset_class = OrganizationFilter
    filter_backends = [backends.DjangoFilterBackend]
    label_expression = 'name'

    def get_queryset(self):
        """
        Override the get_queryset method to filter organizations by the authenticated
        user.
        """
        queryset = super().get_queryset()
        if self.action == 'login':
            if not self.auth_user:
                return queryset.none()
            return queryset.filter(
                members__user_id=self.auth_user.id,
                members__is_active=True,
                is_active=True,
            )
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return OrganizationListSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=['post'])
    def login(self, request, *args, **kwargs):
        """Login to the organization."""
        if not (user := self.auth_user):
            return Response(
                data={'detail': _('User not authenticated.')},
                status=http_status.HTTP_401_UNAUTHORIZED,
            )
        if not (organization := self.get_object()):
            return Response(
                data={'detail': _('Organization not found.')},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        # Set the organization in the session
        request.session['organization_id'] = organization.id

        if member := get_member(request):
            member.last_login_at = timezone.now()
            member.save(update_fields=['last_login_at'])

        data = {
            'user': user,
            'organizations': user.active_organizations,
            'organization': organization,
            'member': member,
        }
        serializer = SessionSerializer(instance=data, context={'request': request})
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)
