from datetime import datetime

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.billing.choices import (
    BillingCycleChoices,
    SubscriptionCourtesyChoices,
    SubscriptionStatusChoices,
)
from apps.billing.managers import SubscriptionQuerySet
from apps.generics.models.abstracts import BaseModel


class Subscription(BaseModel):
    organization = models.OneToOneField(
        to='accounts.Organization',
        on_delete=models.CASCADE,
        related_name='subscription',
        verbose_name=_('Organization'),
    )
    plan = models.ForeignKey(
        to='billing.Plan',
        on_delete=models.PROTECT,
        related_name='subscriptions',
        verbose_name=_('Plan'),
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatusChoices.choices,
        db_index=True,
        verbose_name=_('Status'),
    )
    cycle = models.CharField(
        max_length=10,
        choices=BillingCycleChoices.choices,
        null=True,
        blank=True,
        verbose_name=_('Cycle'),
    )
    trial_ends_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Trial ends at')
    )
    courtesy = models.CharField(
        max_length=10,
        choices=SubscriptionCourtesyChoices.choices,
        blank=True,
        default='',
        verbose_name=_('Courtesy'),
    )

    current_period_start = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Current period start')
    )
    current_period_end = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Current period end')
    )
    cancel_at_period_end = models.BooleanField(
        default=False, verbose_name=_('Cancel at period end')
    )
    scheduled_plan = models.ForeignKey(
        to='billing.Plan',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('Scheduled plan'),
    )
    scheduled_cycle = models.CharField(
        max_length=10,
        choices=BillingCycleChoices.choices,
        null=True,
        blank=True,
        verbose_name=_('Scheduled cycle'),
    )
    pending_plan = models.ForeignKey(
        to='billing.Plan',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('Pending plan'),
    )
    pending_cycle = models.CharField(
        max_length=10,
        choices=BillingCycleChoices.choices,
        null=True,
        blank=True,
        verbose_name=_('Pending cycle'),
    )
    gateway_customer_id = models.CharField(
        max_length=64, blank=True, default='', verbose_name=_('Gateway customer id')
    )
    gateway_subscription_id = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name=_('Gateway subscription id'),
    )
    trial_reminder_sent = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name=_('Trial reminder sent')
    )

    objects = SubscriptionQuerySet.as_manager()

    class Meta:
        verbose_name = _('Subscription')
        verbose_name_plural = _('Subscriptions')
        constraints = [
            models.CheckConstraint(
                condition=~Q(status=SubscriptionStatusChoices.TRIALING)
                | Q(trial_ends_at__isnull=False),
                name='billing_subscription_trial_has_end',
            ),
            models.CheckConstraint(
                condition=Q(cycle__isnull=True, current_period_end__isnull=True)
                | Q(cycle__isnull=False, current_period_end__isnull=False),
                name='billing_subscription_cycle_has_period',
            ),
            models.CheckConstraint(
                condition=Q(scheduled_plan__isnull=True, scheduled_cycle__isnull=True)
                | Q(scheduled_plan__isnull=False, scheduled_cycle__isnull=False),
                name='billing_subscription_scheduled_pair',
            ),
            models.CheckConstraint(
                condition=Q(pending_plan__isnull=True, pending_cycle__isnull=True)
                | Q(pending_plan__isnull=False, pending_cycle__isnull=False),
                name='billing_subscription_pending_pair',
            ),
            models.CheckConstraint(
                condition=Q(cancel_at_period_end=False)
                | Q(scheduled_plan__isnull=True),
                name='billing_subscription_cancel_or_schedule',
            ),
            models.UniqueConstraint(
                fields=['gateway_subscription_id'],
                condition=~Q(gateway_subscription_id=''),
                name='billing_subscription_unique_gateway_id',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.organization_id} · {self.plan_id} · {self.status}'

    @property
    def is_trialing(self) -> bool:
        return self.status == SubscriptionStatusChoices.TRIALING

    @property
    def is_complimentary(self) -> bool:
        return (
            self.status == SubscriptionStatusChoices.ACTIVE
            and self.cycle is None
            and not self.plan.is_free
        )

    @property
    def is_paid(self) -> bool:
        return self.cycle is not None and self.current_period_end is not None

    @property
    def has_pending_change(self) -> bool:
        return self.pending_plan_id is not None

    def paid_period_end(self) -> datetime:
        if self.current_period_end is None:
            raise ValueError('The subscription has no paid period.')
        return self.current_period_end

    def paid_cycle(self) -> str:
        if self.cycle is None:
            raise ValueError('The subscription has no cycle.')
        return self.cycle
