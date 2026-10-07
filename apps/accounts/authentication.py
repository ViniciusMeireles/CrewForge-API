from django.conf import settings
from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.accounts.utils.auth_cookies import enforce_csrf


class JWTCookieAuthentication(JWTAuthentication):
    """Bearer header first; otherwise the HttpOnly access cookie with CSRF checks."""

    def authenticate(self, request):
        if self.get_header(request) is not None:
            return super().authenticate(request)

        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS_NAME)
        if not raw_token:
            return None
        try:
            validated_token = self.get_validated_token(raw_token.encode())
            user = self.get_user(validated_token)
        except InvalidToken, TokenError, AuthenticationFailed:
            return None

        enforce_csrf(request)
        request.authenticated_by_cookie = True
        return user, validated_token


class JWTCookieAuthenticationScheme(SimpleJWTScheme):
    target_class = 'apps.accounts.authentication.JWTCookieAuthentication'
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
