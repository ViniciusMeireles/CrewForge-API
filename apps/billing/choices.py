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


class InvoiceStatusChoices(models.TextChoices):
    PENDING = 'pending', _('Pending')
    PAID = 'paid', _('Paid')
    OVERDUE = 'overdue', _('Overdue')
    REFUNDED = 'refunded', _('Refunded')
    CANCELED = 'canceled', _('Canceled')


class InvoiceKindChoices(models.TextChoices):
    RECURRING = 'recurring', _('Recurring')
    PRORATION = 'proration', _('Proration')


class GatewayChoices(models.TextChoices):
    ASAAS = 'asaas', _('Asaas')
    FAKE = 'fake', _('Fake')


class BrazilStateChoices(models.TextChoices):
    AC = 'AC', 'AC'
    AL = 'AL', 'AL'
    AP = 'AP', 'AP'
    AM = 'AM', 'AM'
    BA = 'BA', 'BA'
    CE = 'CE', 'CE'
    DF = 'DF', 'DF'
    ES = 'ES', 'ES'
    GO = 'GO', 'GO'
    MA = 'MA', 'MA'
    MT = 'MT', 'MT'
    MS = 'MS', 'MS'
    MG = 'MG', 'MG'
    PA = 'PA', 'PA'
    PB = 'PB', 'PB'
    PR = 'PR', 'PR'
    PE = 'PE', 'PE'
    PI = 'PI', 'PI'
    RJ = 'RJ', 'RJ'
    RN = 'RN', 'RN'
    RS = 'RS', 'RS'
    RO = 'RO', 'RO'
    RR = 'RR', 'RR'
    SC = 'SC', 'SC'
    SP = 'SP', 'SP'
    SE = 'SE', 'SE'
    TO = 'TO', 'TO'


class TaxIdKindChoices(models.TextChoices):
    CPF = 'cpf', 'CPF'
    CNPJ = 'cnpj', 'CNPJ'


class ChangeKindChoices(models.TextChoices):
    NEW = 'new', _('New subscription')
    UPGRADE = 'upgrade', _('Upgrade')
    DOWNGRADE = 'downgrade', _('Downgrade')
