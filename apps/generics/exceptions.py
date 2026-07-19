import logging

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

from apps.generics.choices import ErrorCode

logger = logging.getLogger(__name__)


def _get_error_code(exc: APIException) -> ErrorCode:
    mapping = {
        AuthenticationFailed: ErrorCode.AUTHENTICATION_ERROR,
        NotAuthenticated: ErrorCode.AUTHENTICATION_ERROR,
        PermissionDenied: ErrorCode.PERMISSION_DENIED,
        Http404: ErrorCode.NOT_FOUND,
        exceptions.MethodNotAllowed: ErrorCode.METHOD_NOT_ALLOWED,
        exceptions.NotAcceptable: ErrorCode.NOT_ACCEPTABLE,
        exceptions.Throttled: ErrorCode.THROTTLED,
    }
    for exc_type, code in mapping.items():
        if isinstance(exc, exc_type):
            return code
    if isinstance(exc, exceptions.ValidationError):
        return ErrorCode.VALIDATION_ERROR
    return ErrorCode.INTERNAL_ERROR


def _get_error_message(exc: APIException, code: ErrorCode) -> str:
    if code == ErrorCode.VALIDATION_ERROR:
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
        logger.exception('Internal server error: %s', exc)
        return Response(
            {
                'error': {
                    'code': ErrorCode.INTERNAL_ERROR,
                    'message': _('An unexpected error occurred.'),
                    'details': None,
                },
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if (code := _get_error_code(exc)) == ErrorCode.INTERNAL_ERROR:
        logger.exception('Internal server error: %s', exc)
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
