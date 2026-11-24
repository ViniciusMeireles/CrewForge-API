from django.db import models
from django.utils.translation import gettext_lazy as _


class SubscriptionStatusChoices(models.TextChoices):
    TRIALING = 'trialing', _('Trial')
    ACTIVE = 'active', _('Active')


class BillingCycleChoices(models.TextChoices):
    MONTHLY = 'monthly', _('Monthly')
    ANNUAL = 'annual', _('Annual')


class SubscriptionCourtesyChoices(models.TextChoices):
    LEGACY = 'legacy', _('Existing organization')
    PLATFORM = 'platform', _('Set by the platform')


class CurrencyChoices(models.TextChoices):
    BRL = 'BRL', _('Brazilian real')
