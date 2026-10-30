import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_out
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
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
from rest_framework_simplejwt.views import (
    TokenVerifyView as TokenVerifyViewBase,
)

from apps.accounts.exceptions import AccountBlocked
from apps.accounts.serializers.auth import (
    EmailVerificationConfirmSerializer,
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
from apps.accounts.utils.email_verification import (
    mark_email_verified,
    send_verification_email,
    verification_cooldown_remaining,
)
from apps.accounts.utils.language import resolve_recipient_language
from apps.accounts.utils.password_reset import password_reset_link
from apps.accounts.utils.security_log import log_security_event
from apps.accounts.utils.sessions import revoke_sessions

AUTH_SCHEMA_TAGS = [_('Authentication')]


@extend_schema(
    tags=AUTH_SCHEMA_TAGS,
    summary=_('Sign in'),
    description=_(
        'Obtain an access/refresh token pair. With the `X-Auth-Transport: cookie` '
        'header (browsers) the tokens are set as HttpOnly cookies and omitted from '
        'the body, and a CSRF token is required.'
    ),
)
class TokenObtainPairView(AuthThrottleMixin, TokenObtainPairViewBase):
    _serializer_class = jwt_settings.TOKEN_OBTAIN_SERIALIZER

    @staticmethod
    def attempted_user_id(request) -> int | None:
        """Account targeted by a failed sign-in (kept out of the log line)."""
        User = get_user_model()
        username = request.data.get(User.USERNAME_FIELD)
        if not isinstance(username, str) or not username:
            return None
        return (
            User.objects.filter(**{User.USERNAME_FIELD: username})
            .values_list('pk', flat=True)
            .first()
        )

    def post(self, request, *args, **kwargs):
        if wants_cookie_transport(request):
            enforce_csrf(request)
        try:
            response = super().post(request, *args, **kwargs)
        except AccountBlocked:
            log_security_event(
                'account.blocked_sign_in',
                request,
                level=logging.WARNING,
                user_id=self.attempted_user_id(request),
            )
            raise
        except AuthenticationFailed:
            log_security_event(
                'auth.login.failed',
                request,
                level=logging.WARNING,
                audit={'subject_user_id': self.attempted_user_id(request)},
            )
            raise
        log_security_event(
            'auth.login.succeeded',
            request,
            user_id=(response.data.get('auth_user') or {}).get('id'),
        )
        return move_tokens_to_cookies(request, response, response.data)


@extend_schema(
    tags=AUTH_SCHEMA_TAGS,
    request=inline_serializer(
        name='TokenRefreshRequest',
        fields={'refresh': serializers.CharField(required=False)},
    ),
    responses=inline_serializer(
        name='TokenRefresh',
        fields={
            'access': serializers.CharField(required=False),
            'refresh': serializers.CharField(required=False),
        },
    ),
    summary=_('Refresh tokens'),
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
        except (TokenError, AuthenticationFailed) as err:
            exc = InvalidToken(err.args[0]) if isinstance(err, TokenError) else err
            log_security_event('auth.refresh.rejected', request, level=logging.WARNING)
            response = self.handle_exception(exc)
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
    tags=AUTH_SCHEMA_TAGS,
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
    summary=_('Request password reset'),
    description=_("Request a password reset link to be sent to the user's email."),
)
class PasswordResetRequestView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]

    @classmethod
    def post(cls, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.user:
            from apps.accounts.tasks import send_password_reset_email

            send_password_reset_email(
                password_reset_link(serializer.user),
                [serializer.user.email],
                language=resolve_recipient_language(serializer.user),
            )

        log_security_event(
            'auth.password_reset.requested',
            request,
            user_id=serializer.user.pk if serializer.user else None,
        )
        return Response(
            data={
                'detail': _(
                    'If an account exists for this email, a password reset link has '
                    'been sent to it. Please check your inbox.'
                ),
            },
            status=http_status.HTTP_200_OK,
        )


@extend_schema(
    tags=AUTH_SCHEMA_TAGS,
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
    summary=_('Confirm password reset'),
    description=_(
        'Confirm the password reset using the provided token and new password.'
    ),
)
class PasswordResetConfirmView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]

    @classmethod
    def post(cls, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            log_security_event(
                'auth.password_reset.failed', request, level=logging.WARNING
            )
            raise
        user = serializer.user
        new_password = serializer.validated_data.get('new_password')

        user.set_password(new_password)
        user.save()
        revoke_sessions(user)
        log_security_event('auth.password_reset.completed', request, user_id=user.pk)

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
    tags=AUTH_SCHEMA_TAGS,
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
                    name=_('Missing refresh token'),
                    value={'detail': _('Refresh token is required.')},
                    response_only=True,
                ),
                OpenApiExample(
                    name=_('Invalid or expired token'),
                    value={'detail': _('Token is invalid or expired.')},
                    response_only=True,
                ),
            ],
            description=_('Invalid request.'),
        ),
    },
    summary=_('Sign out'),
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
        user_id = None
        if refresh_token := request.data.get('refresh') or cookie_token:
            try:
                token = RefreshToken(refresh_token)
                if (claim := token.get(jwt_settings.USER_ID_CLAIM)) is not None:
                    user_id = int(claim)
                token.blacklist()
            except TokenError:
                error = _('Token is invalid or expired.')
        else:
            error = _('Refresh token is required.')

        user_logged_out.send(sender=type(self), request=request, user=request.user)
        if error and not cookie_mode:
            return Response({'detail': error}, status=http_status.HTTP_400_BAD_REQUEST)

        log_security_event('auth.logout', request, user_id=user_id)
        request.session.flush()
        response = Response(status=http_status.HTTP_204_NO_CONTENT)
        return clear_auth_cookies(response) if cookie_mode else response


@extend_schema(
    tags=AUTH_SCHEMA_TAGS,
    request=EmailVerificationConfirmSerializer,
    responses={
        200: OpenApiResponse(response=None, description=_('Email verified.')),
    },
    summary=_('Confirm email verification'),
    description=_(
        'Confirm the email address with the `uid` and `token` from the verification '
        'link.'
    ),
)
class EmailVerificationConfirmView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailVerificationConfirmSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            log_security_event(
                'auth.email_verification.failed', request, level=logging.WARNING
            )
            raise
        mark_email_verified(serializer.user)
        log_security_event('auth.email.verified', request, user_id=serializer.user.pk)
        return Response(
            data={'detail': _('Your email has been verified.')},
            status=http_status.HTTP_200_OK,
        )


@extend_schema(
    tags=AUTH_SCHEMA_TAGS,
    request=None,
    responses={
        200: OpenApiResponse(response=None, description=_('Verification email sent.')),
        429: OpenApiResponse(
            response=None,
            description=_('A link was sent recently; retry after the cooldown.'),
        ),
    },
    summary=_('Resend verification email'),
    description=_('Send a new verification link to the authenticated user email.'),
)
class EmailVerificationResendView(AuthThrottleMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.email_verified:
            detail = _('Your email is already verified.')
        elif not send_verification_email(request.user):
            return Response(
                data={
                    'detail': _('Please wait before requesting a new link.'),
                    'retry_after_seconds': verification_cooldown_remaining(
                        request.user
                    ),
                },
                status=http_status.HTTP_429_TOO_MANY_REQUESTS,
            )
        else:
            detail = _('A new verification link has been sent to your email.')
        return Response(data={'detail': detail}, status=http_status.HTTP_200_OK)


@extend_schema(tags=AUTH_SCHEMA_TAGS)
@extend_schema(
    tags=AUTH_SCHEMA_TAGS,
    summary=_('Verify token'),
    description=_(
        'Check whether a token is valid: `200` when it is, `401` otherwise. It says '
        'nothing about what the token grants.'
    ),
)
class TokenVerifyView(TokenVerifyViewBase):
    pass
