from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import JsonResponse

OK = {'status': 'ok'}
UNAVAILABLE = {'status': 'unavailable'}


def _ready() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        cache.set('readyz', 1, 5)
        cache.get('readyz')
    except DatabaseError, ConnectionError, OSError:
        return False
    return True


class HealthCheckMiddleware:
    """Answer the container probes before host validation, SSL redirect and auth."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'GET' and request.path == '/healthz':
            return JsonResponse(OK)
        if request.method == 'GET' and request.path == '/readyz':
            if _ready():
                return JsonResponse(OK)
            return JsonResponse(UNAVAILABLE, status=503)
        return self.get_response(request)
