from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.billing.choices import BrazilStateChoices, TaxIdKindChoices
from apps.billing.validators import CPF_LENGTH, validate_postal_code, validate_tax_id
from apps.generics.models.abstracts import BaseModel

REQUIRED_FIELDS = (
    'legal_name',
    'tax_id',
    'email',
    'postal_code',
    'street',
    'number',
    'district',
    'city',
    'state',
)


class BillingProfile(BaseModel):
    organization = models.OneToOneField(
        to='accounts.Organization',
        on_delete=models.CASCADE,
        related_name='billing_profile',
        verbose_name=_('Organization'),
    )
    legal_name = models.CharField(max_length=200, verbose_name=_('Legal name'))
    tax_id = models.CharField(
        max_length=14, validators=[validate_tax_id], verbose_name=_('CPF or CNPJ')
    )
    email = models.EmailField(verbose_name=_('Billing email'))
    postal_code = models.CharField(
        max_length=8, validators=[validate_postal_code], verbose_name=_('Postal code')
    )
    street = models.CharField(max_length=200, verbose_name=_('Street'))
    number = models.CharField(max_length=20, verbose_name=_('Number'))
    complement = models.CharField(
        max_length=100, blank=True, default='', verbose_name=_('Complement')
    )
    district = models.CharField(max_length=100, verbose_name=_('District'))
    city = models.CharField(max_length=100, verbose_name=_('City'))
    state = models.CharField(
        max_length=2, choices=BrazilStateChoices.choices, verbose_name=_('State')
    )

    class Meta:
        verbose_name = _('Billing profile')
        verbose_name_plural = _('Billing profiles')

    def __str__(self) -> str:
        return self.legal_name

    @property
    def is_complete(self) -> bool:
        return all(getattr(self, name) for name in REQUIRED_FIELDS)

    @property
    def tax_id_kind(self) -> str:
        return (
            TaxIdKindChoices.CPF
            if len(self.tax_id) == CPF_LENGTH
            else TaxIdKindChoices.CNPJ
        )

    @property
    def masked_tax_id(self) -> str:
        d = self.tax_id
        if self.tax_id_kind == TaxIdKindChoices.CPF:
            return f'CPF {d[0:3]}.{d[3:6]}.***-**'
        return f'CNPJ {d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-**'
