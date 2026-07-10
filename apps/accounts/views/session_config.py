from django.conf import settings
from django.middleware.csrf import get_token
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.serializers.session import SessionConfigSerializer


@extend_schema(
    tags=[str(_('Session'))],
    description=_(
        'Return current cookie and CORS configuration for frontend debugging. '
        'This endpoint is intentionally public so the frontend can verify '
        'connectivity before authentication is established.'
    ),
    responses={200: SessionConfigSerializer},
)
@api_view(['GET'])
@permission_classes([AllowAny])
def session_config(request):
    get_token(request)

    data = {
        'cookie_settings': {
            'session_cookie_samesite': settings.SESSION_COOKIE_SAMESITE,
            'session_cookie_secure': settings.SESSION_COOKIE_SECURE,
            'csrf_cookie_samesite': settings.CSRF_COOKIE_SAMESITE,
            'csrf_cookie_secure': settings.CSRF_COOKIE_SECURE,
        },
        'cors_allowed_origins': settings.CORS_ALLOWED_ORIGINS,
        'cors_allow_credentials': settings.CORS_ALLOW_CREDENTIALS,
        'session_configured': (
            request.session.get('organization_id') is not None
            and request.user.is_authenticated
        ),
        'debug': settings.DEBUG,
    }

    serializer = SessionConfigSerializer(instance=data)
    return Response(serializer.data)
