import re
import uuid

from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import JsonResponse
from redis.exceptions import RedisError

from apps.generics.logging import request_id_var

OK = {'status': 'ok'}
UNAVAILABLE = {'status': 'unavailable'}


def _ready() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        cache.set('readyz', 1, 5)
        return cache.get('readyz') == 1
    except DatabaseError, RedisError, ConnectionError, OSError:
        return False


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


REQUEST_ID_HEADER = 'X-Request-ID'
VALID_REQUEST_ID = re.compile(r'[A-Za-z0-9._-]{1,64}')


class RequestIdMiddleware:
    """Keep a valid incoming ``X-Request-ID`` or create one, for logs and response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get(REQUEST_ID_HEADER, '')
        request_id = (
            incoming if VALID_REQUEST_ID.fullmatch(incoming) else str(uuid.uuid4())
        )
        request.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[REQUEST_ID_HEADER] = request_id
        return response
