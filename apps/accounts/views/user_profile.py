from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.serializers.user_profile import (
    ChangePasswordSerializer,
    UserProfileSerializer,
)
from apps.generics.utils.schema import (
    extend_schema_partial_update,
    extend_schema_retrieve,
)

User = get_user_model()


@extend_schema_view(
    retrieve=extend_schema_retrieve(
        model=User,
        description=_('Retrieve the authenticated user profile.'),
    ),
    partial_update=extend_schema_partial_update(
        model=User,
        description=_('Partially update the authenticated user profile.'),
    ),
)
class UserProfileViewSet(viewsets.GenericViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch', 'post', 'options']

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(
        description=_('Change the authenticated user password.'),
        tags=User.schema_tags(),
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(
                description=_('Password changed successfully.'),
            ),
        },
    )
    @action(
        detail=False,
        methods=['post'],
        url_path='change-password',
        url_name='change-password',
        permission_classes=[IsAuthenticated],
        serializer_class=ChangePasswordSerializer,
    )
    def change_password(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            data={'detail': _('Password changed successfully.')},
            status=status.HTTP_200_OK,
        )
