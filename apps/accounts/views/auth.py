from django.conf import settings
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status as http_status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import (
    TokenObtainPairView as TokenObtainPairViewBase,
)

from apps.accounts.serializers.auth import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)
from apps.accounts.settings import api_settings


class TokenObtainPairView(TokenObtainPairViewBase):
    _serializer_class = api_settings.TOKEN_OBTAIN_SERIALIZER


@extend_schema(
    request=PasswordResetRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=None,
            description=_(
                'Password reset link has been sent to your email. Please check '
                'your inbox.'
            ),
        ),
    },
    description=_("Request a password reset link to be sent to the user's email."),
)
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    @classmethod
    def post(cls, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.data.get('email')

        uid = serializer.data.get('uid')
        token = serializer.data.get('token')

        from apps.accounts.tasks import send_password_reset_email

        reset_link = f'{settings.FRONTEND_RESET_URL}?uid={uid}&token={token}'
        send_password_reset_email(reset_link, [email])

        return Response(
            data={
                'detail': _(
                    'Password reset link has been sent to your email. Please check '
                    'your inbox.'
                ),
            },
            status=http_status.HTTP_200_OK,
        )


@extend_schema(
    request=PasswordResetConfirmSerializer,
    responses={
        200: OpenApiResponse(
            response=None,
            description=_(
                'Your password has been successfully reset. You can now log in with '
                'your new password.'
            ),
        ),
    },
    description=_(
        'Confirm the password reset using the provided token and new password.'
    ),
)
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @classmethod
    def post(cls, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user
        new_password = serializer.validated_data.get('new_password')

        user.set_password(new_password)
        user.save()

        return Response(
            data={
                'detail': _(
                    'Your password has been successfully reset. You can now log in '
                    'with your new password.'
                ),
            },
            status=http_status.HTTP_200_OK,
        )
