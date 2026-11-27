from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.billing.entitlements import BYTES_PER_MB, MAX_MEMBERS, MAX_TEAMS
from apps.generics.choices import ErrorCode
from apps.generics.errors import CodedErrorMixin

STORAGE_BYTES = 'storage_bytes'
MB_PER_GB = 1024


class PlanLimitReached(Exception):
    def __init__(self, key: str, current: int, maximum: int) -> None:
        super().__init__(key)
        self.key = key
        self.current = current
        self.maximum = maximum


def _limit_message(key: str, maximum: int) -> str:
    if key == MAX_MEMBERS:
        return ngettext(
            'Your plan allows up to %(max)s member.',
            'Your plan allows up to %(max)s members.',
            maximum,
        ) % {'max': maximum}
    if key == MAX_TEAMS:
        return ngettext(
            'Your plan allows up to %(max)s team.',
            'Your plan allows up to %(max)s teams.',
            maximum,
        ) % {'max': maximum}
    return _('Your plan allows up to %(max)s of storage.') % {
        'max': format_storage(maximum)
    }


def format_storage(size: int) -> str:
    megabytes = size // BYTES_PER_MB
    if megabytes >= MB_PER_GB and megabytes % MB_PER_GB == 0:
        return f'{megabytes // MB_PER_GB} GB'
    return f'{megabytes} MB'


class PlanLimitReachedError(CodedErrorMixin, PermissionDenied):
    default_code = 'plan_limit_reached'
    error_code = ErrorCode.PLAN_LIMIT_REACHED

    @classmethod
    def from_limit(cls, limit: PlanLimitReached) -> PlanLimitReachedError:
        return cls(
            detail=_limit_message(limit.key, limit.maximum),
            details={
                'limit': limit.key,
                'current': limit.current,
                'max': limit.maximum,
            },
        )


class PlanFeatureUnavailableError(CodedErrorMixin, PermissionDenied):
    default_detail = _('This feature is not included in your plan.')
    default_code = 'plan_feature_unavailable'
    error_code = ErrorCode.PLAN_FEATURE_UNAVAILABLE


class BillingProfileRequiredError(CodedErrorMixin, ValidationError):
    default_detail = _('Fill in your billing details before choosing a paid plan.')
    default_code = 'billing_profile_required'
    error_code = ErrorCode.BILLING_PROFILE_REQUIRED


class GatewayUnavailableError(CodedErrorMixin, APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = _(
        'The payment service is unavailable. Try again in a few minutes.'
    )
    default_code = 'gateway_unavailable'
    error_code = ErrorCode.GATEWAY_UNAVAILABLE


class UnknownGatewayPayment(Exception):
    """A gateway payment that matches no local Subscription."""
