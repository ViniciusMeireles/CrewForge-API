from django.db import models
from django.utils.translation import gettext_lazy as _


class ErrorCode(models.TextChoices):
    AUTHENTICATION_ERROR = 'AUTHENTICATION_ERROR', _('Authentication error')
    PERMISSION_DENIED = 'PERMISSION_DENIED', _('Permission denied')
    NOT_FOUND = 'NOT_FOUND', _('Not found')
    METHOD_NOT_ALLOWED = 'METHOD_NOT_ALLOWED', _('Method not allowed')
    NOT_ACCEPTABLE = 'NOT_ACCEPTABLE', _('Not acceptable')
    THROTTLED = 'THROTTLED', _('Throttled')
    VALIDATION_ERROR = 'VALIDATION_ERROR', _('Validation error')
    INTERNAL_ERROR = 'INTERNAL_ERROR', _('Internal error')
