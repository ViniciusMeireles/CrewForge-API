from django.conf import settings
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.settings import api_settings as jwt_settings

COOKIE_TRANSPORT = 'cookie'


def wants_cookie_transport(request) -> bool:
    header = request.headers.get(settings.AUTH_TRANSPORT_HEADER, '')
    return header.lower() == COOKIE_TRANSPORT or bool(
        getattr(request, 'authenticated_by_cookie', False)
    )


def enforce_csrf(request) -> None:
    check = CSRFCheck(lambda _request: None)
    check.process_request(request)
    if reason := check.process_view(request, None, (), {}):
        raise PermissionDenied(format_lazy(_('CSRF Failed: {reason}'), reason=reason))


def _cookie_options(path: str) -> dict:
    return {
        'path': path,
        'secure': settings.AUTH_COOKIE_SECURE,
        'httponly': True,
        'samesite': settings.AUTH_COOKIE_SAMESITE,
    }


def set_auth_cookies(response, access: str | None, refresh: str | None):
    if access:
        response.set_cookie(
            settings.AUTH_COOKIE_ACCESS_NAME,
            access,
            max_age=int(jwt_settings.ACCESS_TOKEN_LIFETIME.total_seconds()),
            **_cookie_options('/'),
        )
    if refresh:
        response.set_cookie(
            settings.AUTH_COOKIE_REFRESH_NAME,
            refresh,
            max_age=int(jwt_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
            **_cookie_options(settings.AUTH_COOKIE_REFRESH_PATH),
        )
    return response


def clear_auth_cookies(response):
    response.delete_cookie(
        settings.AUTH_COOKIE_ACCESS_NAME,
        path='/',
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        settings.AUTH_COOKIE_REFRESH_NAME,
        path=settings.AUTH_COOKIE_REFRESH_PATH,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return response


def refresh_cookie(request) -> str | None:
    return request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME) or None


def pop_tokens(container: dict) -> tuple[str | None, str | None]:
    return container.pop('access', None), container.pop('refresh', None)


def move_tokens_to_cookies(request, response, container: dict | None):
    """In cookie transport, move ``access`` and ``refresh`` into cookies."""
    if container is None or not wants_cookie_transport(request):
        return response
    return set_auth_cookies(response, *pop_tokens(container))


def move_auth_token_to_cookies(request, response, user_data: dict | None):
    """In cookie transport, move ``user_data['auth_token']`` to cookies."""
    if user_data is None or not wants_cookie_transport(request):
        return response
    tokens = user_data.pop('auth_token', None) or {}
    return set_auth_cookies(response, tokens.get('access'), tokens.get('refresh'))
