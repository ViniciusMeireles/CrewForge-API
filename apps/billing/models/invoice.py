from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.billing.choices import (
    BillingCycleChoices,
    GatewayChoices,
    InvoiceKindChoices,
    InvoiceStatusChoices,
)
from apps.billing.managers import InvoiceQuerySet
from apps.generics.models.abstracts import BaseModel


class Invoice(BaseModel):
    subscription = models.ForeignKey(
        to='billing.Subscription',
        on_delete=models.PROTECT,
        related_name='invoices',
        verbose_name=_('Subscription'),
    )
    gateway = models.CharField(
        max_length=20, choices=GatewayChoices.choices, verbose_name=_('Gateway')
    )
    gateway_id = models.CharField(max_length=64, verbose_name=_('Gateway id'))
    kind = models.CharField(
        max_length=20, choices=InvoiceKindChoices.choices, verbose_name=_('Kind')
    )
    plan = models.ForeignKey(
        to='billing.Plan',
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name=_('Plan'),
    )
    cycle = models.CharField(
        max_length=10, choices=BillingCycleChoices.choices, verbose_name=_('Cycle')
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_('Amount')
    )
    issued_at = models.DateTimeField(verbose_name=_('Issued at'))
    due_date = models.DateField(verbose_name=_('Due date'))
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Paid at'))
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatusChoices.choices,
        db_index=True,
        verbose_name=_('Status'),
    )
    payment_url = models.URLField(
        max_length=500, blank=True, default='', verbose_name=_('Payment URL')
    )
    period_start = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Period start')
    )
    period_end = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Period end')
    )
    nfse_number = models.CharField(
        max_length=50, blank=True, default='', verbose_name=_('NFS-e number')
    )
    nfse_url = models.URLField(
        max_length=500, blank=True, default='', verbose_name=_('NFS-e URL')
    )

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        ordering = ['-issued_at', '-id']
        verbose_name = _('Invoice')
        verbose_name_plural = _('Invoices')
        constraints = [
            models.UniqueConstraint(
                fields=['gateway', 'gateway_id'], name='billing_invoice_unique_gateway'
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=Decimal('0')),
                name='billing_invoice_amount_positive',
            ),
        ]
        indexes = [
            models.Index(
                fields=['subscription', '-issued_at'],
                name='billing_invoice_sub_issued',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.gateway}:{self.gateway_id} · {self.status}'

    @property
    def description(self) -> str:
        if self.kind == InvoiceKindChoices.PRORATION:
            return str(_('Plan change adjustment'))
        if self.cycle == BillingCycleChoices.ANNUAL:
            return str(_('Annual subscription'))
        return str(_('Monthly subscription'))

    @property
    def is_open(self) -> bool:
        return self.status in (
            InvoiceStatusChoices.PENDING,
            InvoiceStatusChoices.OVERDUE,
        )
