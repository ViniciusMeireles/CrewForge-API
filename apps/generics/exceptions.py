from django.http import Http404
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler


def _get_error_code(exc: APIException) -> str:
    mapping = {
        AuthenticationFailed: 'AUTHENTICATION_ERROR',
        NotAuthenticated: 'AUTHENTICATION_ERROR',
        PermissionDenied: 'PERMISSION_DENIED',
        Http404: 'NOT_FOUND',
        exceptions.MethodNotAllowed: 'METHOD_NOT_ALLOWED',
        exceptions.NotAcceptable: 'NOT_ACCEPTABLE',
        exceptions.Throttled: 'THROTTLED',
    }
    for exc_type, code in mapping.items():
        if isinstance(exc, exc_type):
            return code
    if isinstance(exc, exceptions.ValidationError):
        return 'VALIDATION_ERROR'
    return 'INTERNAL_ERROR'


def _get_error_message(exc: APIException, code: str) -> str:
    if code == 'VALIDATION_ERROR':
        return _('One or more fields are invalid.')
    if isinstance(exc, APIException) and hasattr(exc, 'detail'):
        detail = exc.detail
        if isinstance(detail, str):
            return detail
        if isinstance(detail, dict):
            for messages in detail.values():
                if isinstance(messages, list) and messages:
                    return str(messages[0])
                if isinstance(messages, str):
                    return messages
                break
        if isinstance(detail, list) and detail:
            first = detail[0]
            if isinstance(first, str):
                return first
            if isinstance(first, list) and first:
                return str(first[0])
            return str(first)
    return str(exc)


def _get_error_details(exc: APIException) -> dict | None:
    if not isinstance(exc, exceptions.ValidationError):
        return None
    detail = exc.detail
    if isinstance(detail, dict):
        return detail
    if isinstance(detail, list):
        return {'non_field_errors': detail}
    return None


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return Response(
            {
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': _('An unexpected error occurred.'),
                    'details': None,
                },
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    code = _get_error_code(exc)
    message = _get_error_message(exc, code)
    details = _get_error_details(exc)

    response.data = {
        'error': {
            'code': code,
            'message': message,
            'details': details,
        },
    }

    return response
