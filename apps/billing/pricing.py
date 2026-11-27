import calendar
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from apps.billing.choices import BillingCycleChoices, ChangeKindChoices
from apps.billing.models.plan import Plan
from apps.billing.models.subscription import Subscription

CENT = Decimal('0.01')
MONTHS: dict[str, int] = {
    BillingCycleChoices.MONTHLY: 1,
    BillingCycleChoices.ANNUAL: 12,
}


def price(plan: Plan, cycle: str) -> Decimal | None:
    return (
        plan.annual_price if cycle == BillingCycleChoices.ANNUAL else plan.monthly_price
    )


def required_price(plan: Plan, cycle: str) -> Decimal:
    value = price(plan, cycle)
    if value is None:
        raise ValidationError({'cycle': [_('This plan is not offered in this cycle.')]})
    return value


def monthly_equivalent(plan: Plan, cycle: str) -> Decimal:
    value = price(plan, cycle) or Decimal('0')
    return value / MONTHS[cycle]


def add_months(moment: datetime, months: int) -> datetime:
    month_index = moment.month - 1 + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def period_end(start: datetime, cycle: str) -> datetime:
    return add_months(start, MONTHS[cycle])


def classify(subscription: Subscription, plan: Plan, cycle: str) -> str:
    if plan.is_free:
        raise ValidationError(
            {'plan': [_('To move to the free plan, cancel your subscription.')]}
        )
    if price(plan, cycle) is None:
        raise ValidationError({'cycle': [_('This plan is not offered in this cycle.')]})
    if not subscription.is_paid:
        return ChangeKindChoices.NEW
    if subscription.plan_id == plan.pk and subscription.cycle == cycle:
        raise ValidationError({'plan': [_('This is already your plan and cycle.')]})
    current = monthly_equivalent(subscription.plan, subscription.paid_cycle())
    target = monthly_equivalent(plan, cycle)
    annual_switch = (
        subscription.cycle == BillingCycleChoices.MONTHLY
        and cycle == BillingCycleChoices.ANNUAL
    )
    monthly_switch = (
        subscription.cycle == BillingCycleChoices.ANNUAL
        and cycle == BillingCycleChoices.MONTHLY
    )
    if monthly_switch or (target < current and not annual_switch):
        return ChangeKindChoices.DOWNGRADE
    return ChangeKindChoices.UPGRADE


def proration(
    subscription: Subscription, plan: Plan, cycle: str, now: datetime
) -> Decimal:
    start = subscription.current_period_start
    end = subscription.current_period_end
    if start is None or end is None or now >= end:
        return Decimal('0.00')
    period_seconds = (end - start).total_seconds()
    remaining = (end - now).total_seconds()
    current_price = price(subscription.plan, subscription.paid_cycle()) or Decimal('0')
    if cycle == subscription.cycle:
        delta = (price(plan, cycle) or Decimal('0')) - current_price
        amount = delta * Decimal(remaining) / Decimal(period_seconds)
    else:
        credit = current_price * Decimal(remaining) / Decimal(period_seconds)
        amount = (price(plan, cycle) or Decimal('0')) - credit
    return max(amount, Decimal('0')).quantize(CENT, rounding=ROUND_HALF_UP)
