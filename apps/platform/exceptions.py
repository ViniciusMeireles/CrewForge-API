from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied

from apps.generics.choices import ErrorCode
from apps.generics.errors import CodedErrorMixin


class ReadOnlyImpersonation(CodedErrorMixin, PermissionDenied):
    default_detail = _('Read-only while viewing as another user')
    default_code = 'read_only_impersonation'
    error_code = ErrorCode.READ_ONLY_IMPERSONATION


class ImpersonationEnded(CodedErrorMixin, PermissionDenied):
    default_code = 'impersonation_ended'
    error_code = ErrorCode.IMPERSONATION_ENDED
