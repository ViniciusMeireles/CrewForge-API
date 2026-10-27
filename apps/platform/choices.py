from django.db import models
from django.utils.translation import gettext_lazy as _


class ImpersonationEndReasonChoices(models.TextChoices):
    EXIT = 'exit', _('Exit')
    EXPIRED = 'expired', _('Expired')
    USER_BLOCKED = 'user_blocked', _('User blocked')
    SIGNED_OUT = 'signed_out', _('Signed out')
