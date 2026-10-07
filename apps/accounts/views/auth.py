from django.conf import settings
from django.utils.translation import gettext as _
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (
    TokenObtainPairView as TokenObtainPairViewBase,
)
from rest_framework_simplejwt.views import (
    TokenRefreshView as TokenRefreshViewBase,
)

from apps.accounts.serializers.auth import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)
from apps.accounts.settings import jwt_settings
from apps.accounts.throttles import AuthRefreshThrottleMixin, AuthThrottleMixin
from apps.accounts.utils.auth_cookies import (
    clear_auth_cookies,
    enforce_csrf,
    move_tokens_to_cookies,
    refresh_cookie,
    set_auth_cookies,
    wants_cookie_transport,
)


@extend_schema(
    description=_(
        'Obtain an access/refresh token pair. With the `X-Auth-Transport: cookie` '
        'header (browsers) the tokens are set as HttpOnly cookies and omitted from '
        'the body, and a CSRF token is required.'
    ),
)
class TokenObtainPairView(AuthThrottleMixin, TokenObtainPairViewBase):
    _serializer_class = jwt_settings.TOKEN_OBTAIN_SERIALIZER

    def post(self, request, *args, **kwargs):
        if wants_cookie_transport(request):
            enforce_csrf(request)
        response = super().post(request, *args, **kwargs)
        return move_tokens_to_cookies(request, response, response.data)


@extend_schema(
    request=inline_serializer(
        name='TokenRefreshRequest',
        fields={'refresh': serializers.CharField(required=False)},
    ),
    description=_(
        'Rotate the refresh token. Send `refresh` in the body (Bearer clients) or '
        'rely on the refresh cookie (browsers). A refresh read from the cookie is '
        'answered with new cookies and never with tokens in the body; it requires a '
        'CSRF token.'
    ),
)
class TokenRefreshView(AuthRefreshThrottleMixin, TokenRefreshViewBase):
    def post(self, request, *args, **kwargs):
        cookie_token = None if 'refresh' in request.data else refresh_cookie(request)
        cookie_mode = cookie_token is not None or wants_cookie_transport(request)
        if cookie_mode:
            enforce_csrf(request)

        data = {'refresh': cookie_token} if cookie_token else request.data
        serializer = self.get_serializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as err:
            response = self.handle_exception(InvalidToken(err.args[0]))
            return clear_auth_cookies(response) if cookie_mode else response

        response = Response(serializer.validated_data, status=http_status.HTTP_200_OK)
        if cookie_mode:
            response.data = {}
            set_auth_cookies(
                response,
                serializer.validated_data.get('access'),
                serializer.validated_data.get('refresh'),
            )
        return response


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
class PasswordResetRequestView(AuthThrottleMixin, APIView):
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
class PasswordResetConfirmView(AuthThrottleMixin, APIView):
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


@extend_schema(
    request=inline_serializer(
        name='LogoutRequest',
        fields={
            'refresh': serializers.CharField(required=False),
        },
    ),
    responses={
        http_status.HTTP_204_NO_CONTENT: OpenApiResponse(
            response=None,
            description=_('Logout successful.'),
        ),
        http_status.HTTP_400_BAD_REQUEST: OpenApiResponse(
            response=inline_serializer(
                name='LogoutErrorResponse',
                fields={
                    'detail': serializers.CharField(),
                },
            ),
            examples=[
                OpenApiExample(
                    name=str(_('Missing refresh token')),
                    value={'detail': _('Refresh token is required.')},
                    response_only=True,
                ),
                OpenApiExample(
                    name=str(_('Invalid or expired token')),
                    value={'detail': _('Token is invalid or expired.')},
                    response_only=True,
                ),
            ],
            description=_('Invalid request.'),
        ),
    },
    description=_(
        'Blacklist the refresh token and clear the organization session. Browsers '
        '(refresh cookie or `X-Auth-Transport: cookie`) may omit `refresh`; the auth '
        'cookies are always cleared and a CSRF token is required.'
    ),
)
class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        cookie_token = refresh_cookie(request)
        cookie_mode = cookie_token is not None or wants_cookie_transport(request)
        if cookie_mode:
            enforce_csrf(request)

        error = None
        if refresh_token := request.data.get('refresh') or cookie_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                error = _('Token is invalid or expired.')
        else:
            error = _('Refresh token is required.')

        if error and not cookie_mode:
            return Response({'detail': error}, status=http_status.HTTP_400_BAD_REQUEST)

        request.session.flush()
        response = Response(status=http_status.HTTP_204_NO_CONTENT)
        return clear_auth_cookies(response) if cookie_mode else response
