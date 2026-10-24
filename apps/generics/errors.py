from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, status
from rest_framework.exceptions import APIException

from apps.generics.choices import ErrorCode


class CodedErrorMixin:
    """An API exception that names its own ``ErrorCode`` and ``details``."""

    error_code: ErrorCode
    error_details: dict | None = None

    def __init__(self, detail=None, code=None, details: dict | None = None):
        super().__init__(detail, code)
        if details is not None:
            self.error_details = details


class InvalidState(CodedErrorMixin, APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('This action is not allowed in the current state.')
    default_code = 'invalid_state'
    error_code = ErrorCode.INVALID_STATE


class CooldownThrottled(exceptions.Throttled):
    """429 with ``details.retry_after_seconds`` for a per-object cooldown."""

    error_code = ErrorCode.THROTTLED

    def __init__(self, detail, retry_after_seconds: int):
        super().__init__(detail=detail)
        self.wait = retry_after_seconds
        self.error_details = {'retry_after_seconds': retry_after_seconds}
