from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.generics.choices import ErrorCode
from apps.generics.errors import CodedErrorMixin


class AccountBlocked(CodedErrorMixin, AuthenticationFailed):
    default_detail = _('Your account is blocked. Contact support.')
    default_code = 'account_blocked'
    error_code = ErrorCode.ACCOUNT_BLOCKED


class OrganizationSuspended(CodedErrorMixin, PermissionDenied):
    default_detail = _('This organization is suspended. Contact support.')
    default_code = 'organization_suspended'
    error_code = ErrorCode.ORGANIZATION_SUSPENDED
