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
