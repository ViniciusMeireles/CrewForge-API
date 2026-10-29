from django.conf import settings
from django.utils.translation import gettext_lazy as _
from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.accounts.exceptions import AccountBlocked
from apps.accounts.utils.auth_cookies import enforce_csrf
from apps.accounts.utils.sessions import is_token_revoked


class JWTCookieAuthentication(JWTAuthentication):
    """
    Bearer header first; otherwise the HttpOnly access cookie with CSRF checks.

    A token issued before the User's sessions were revoked is invalid, so the stale
    cookie of a blocked User is ignored like any expired one (logout and public routes
    keep working). A blocked User with a token issued afterwards is refused with
    ``ACCOUNT_BLOCKED`` on both paths.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if is_token_revoked(user, validated_token):
            raise AuthenticationFailed(_('Your session has ended. Sign in again.'))
        if user.is_blocked:
            raise AccountBlocked()
        return user

    def authenticate(self, request):
        if self.get_header(request) is not None:
            return super().authenticate(request)

        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS_NAME)
        if not raw_token:
            return None
        try:
            validated_token = self.get_validated_token(raw_token.encode())
            user = self.get_user(validated_token)
        except AccountBlocked:
            raise
        except InvalidToken, TokenError, AuthenticationFailed:
            return None

        enforce_csrf(request)
        request.authenticated_by_cookie = True
        return user, validated_token


def user_authentication_rule(user) -> bool:
    """
    simplejwt ``USER_AUTHENTICATION_RULE`` for sign-in and token refresh.

    Called only after the password (or refresh token) is accepted, so a blocked
    account learns it is blocked (BR-22) while a wrong password keeps the generic
    error.
    """
    if user is not None and user.is_active and user.is_blocked:
        raise AccountBlocked()
    return user is not None and user.is_active


class JWTCookieAuthenticationScheme(SimpleJWTScheme):
    target_class = 'apps.accounts.authentication.JWTCookieAuthentication'
    match_subclasses = True
    name = ['jwtAuth', 'jwtCookieAuth']

    def get_security_definition(self, auto_schema):
        return [
            super().get_security_definition(auto_schema),
            {
                'type': 'apiKey',
                'in': 'cookie',
                'name': settings.AUTH_COOKIE_ACCESS_NAME,
            },
        ]
