from django.conf import settings
from rest_framework.permissions import BasePermission


def api_docs_public() -> bool:
    public = getattr(settings, 'API_DOCS_PUBLIC', None)
    return settings.DEBUG if public is None else public


class ApiDocsPermission(BasePermission):
    """Serve the API schema and docs publicly only when enabled, else to staff."""

    def has_permission(self, request, view):
        if api_docs_public():
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)
