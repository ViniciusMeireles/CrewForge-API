from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.billing.choices import CurrencyChoices
from apps.billing.entitlements import validate_entitlements
from apps.billing.managers import PlanQuerySet
from apps.generics.models.abstracts import BaseModel

ZERO = Decimal('0')


class Plan(BaseModel):
    code = models.SlugField(
        max_length=50,
        unique=True,
        verbose_name=_('Code'),
        help_text=_('Unique, stable identifier of the plan'),
    )
    name = models.CharField(max_length=100, verbose_name=_('Name'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Monthly price'),
    )
    annual_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Annual price'),
    )
    currency = models.CharField(
        max_length=3,
        choices=CurrencyChoices.choices,
        default=CurrencyChoices.BRL,
        verbose_name=_('Currency'),
    )
    trial_days = models.PositiveSmallIntegerField(
        default=0, verbose_name=_('Trial days')
    )
    is_public = models.BooleanField(
        default=True,
        verbose_name=_('Is public'),
        help_text=_('Offered for self-service'),
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_('Is default'),
        help_text=_('The plan new organizations try'),
    )
    is_free = models.BooleanField(
        default=False,
        verbose_name=_('Is free'),
        help_text=_('The fallback plan'),
    )
    included_seats = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_('Included seats')
    )
    extra_seat_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Extra seat price'),
    )
    entitlements = models.JSONField(
        default=dict, blank=True, verbose_name=_('Entitlements')
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0, verbose_name=_('Sort order')
    )

    objects = PlanQuerySet.as_manager()

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = _('Plan')
        verbose_name_plural = _('Plans')
        constraints = [
            models.UniqueConstraint(
                fields=['is_default'],
                condition=Q(is_default=True),
                name='billing_plan_single_default',
            ),
            models.UniqueConstraint(
                fields=['is_free'],
                condition=Q(is_free=True),
                name='billing_plan_single_free',
            ),
            models.CheckConstraint(
                condition=(
                    (Q(monthly_price__isnull=True) | Q(monthly_price__gte=ZERO))
                    & (Q(annual_price__isnull=True) | Q(annual_price__gte=ZERO))
                    & (Q(extra_seat_price__isnull=True) | Q(extra_seat_price__gte=ZERO))
                ),
                name='billing_plan_prices_not_negative',
            ),
            models.CheckConstraint(
                condition=Q(is_free=False) | Q(monthly_price=ZERO, annual_price=ZERO),
                name='billing_plan_free_costs_nothing',
            ),
            models.CheckConstraint(
                condition=Q(is_default=False) | Q(trial_days__gt=0),
                name='billing_plan_default_has_trial',
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        validate_entitlements(self.entitlements)
