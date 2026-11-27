import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from apps.accounts.models.organization import Organization
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.services import record_audit_event
from apps.billing import emails, pricing
from apps.billing.choices import (
    BillingCycleChoices,
    ChangeKindChoices,
    InvoiceKindChoices,
    InvoiceStatusChoices,
    SubscriptionStatusChoices,
)
from apps.billing.exceptions import (
    BillingProfileRequiredError,
    GatewayUnavailableError,
    UnknownGatewayPayment,
)
from apps.billing.gateways import get_gateway
from apps.billing.gateways.base import CustomerData, GatewayError, GatewayPayment
from apps.billing.models.billing_profile import BillingProfile
from apps.billing.models.invoice import Invoice
from apps.billing.models.plan import Plan
from apps.billing.models.subscription import Subscription
from apps.generics.errors import InvalidState

logger = logging.getLogger(__name__)

PROFILE_FIELDS = (
    'legal_name',
    'tax_id',
    'email',
    'postal_code',
    'street',
    'number',
    'complement',
    'district',
    'city',
    'state',
)
REFERENCE_PREFIX = 'crewforge-subscription-'


@dataclass(frozen=True)
class ChangePreview:
    kind: str
    charged_now: Decimal
    recurring_amount: Decimal
    recurring_from: date
    effective_at: datetime
    requires_billing_profile: bool


def reference(subscription: Subscription) -> str:
    return f'{REFERENCE_PREFIX}{subscription.pk}'


def subscription_id_from_reference(value: str) -> int | None:
    if not value.startswith(REFERENCE_PREFIX):
        return None
    suffix = value.removeprefix(REFERENCE_PREFIX)
    return int(suffix) if suffix.isdigit() else None


def locked_subscription(organization: Organization) -> Subscription:
    subscription = (
        Subscription.objects.select_for_update(of=('self',))
        .select_related('plan', 'organization')
        .filter(organization=organization)
        .first()
    )
    if subscription is None:
        raise InvalidState(_('This organization has no subscription.'))
    return subscription


def billing_profile(organization: Organization) -> BillingProfile | None:
    return BillingProfile.objects.filter(organization=organization).first()


def _gateway_call(call):
    try:
        return call()
    except GatewayError as error:
        logger.warning('billing.gateway_error', extra={'error': str(error)})
        raise GatewayUnavailableError() from error


def _customer_data(profile: BillingProfile, subscription: Subscription) -> CustomerData:
    return CustomerData(
        name=profile.legal_name,
        tax_id=profile.tax_id,
        email=profile.email,
        postal_code=profile.postal_code,
        street=profile.street,
        number=profile.number,
        complement=profile.complement,
        district=profile.district,
        external_reference=reference(subscription),
    )


def _ensure_customer(
    gateway, subscription: Subscription, profile: BillingProfile
) -> str:
    if subscription.gateway_customer_id:
        return subscription.gateway_customer_id
    customer_id = _gateway_call(
        lambda: gateway.upsert_customer(_customer_data(profile, subscription))
    )
    subscription.gateway_customer_id = customer_id
    return customer_id


def _description(plan: Plan, cycle: str) -> str:
    return f'{plan.name} · {BillingCycleChoices(cycle).label}'


def _record(
    action,
    subscription: Subscription,
    *,
    request=None,
    actor_member=None,
    system=False,
    metadata=None,
    changes=(),
):
    record_audit_event(
        action,
        request=None if system else request,
        organization_id=subscription.organization_id,
        target=subscription.organization,
        actor_member=None if system else actor_member,
        actor_type=AuditActorTypeChoices.SYSTEM if system else None,
        metadata=metadata or {},
        changes=changes,
    )


def _plan_changes(
    before_plan: Plan, before_cycle, after_plan: Plan, after_cycle
) -> list[dict]:
    changes = []
    if before_plan.pk != after_plan.pk:
        changes.append(
            {'field': 'plan', 'before': before_plan.code, 'after': after_plan.code}
        )
    if before_cycle != after_cycle:
        changes.append({'field': 'cycle', 'before': before_cycle, 'after': after_cycle})
    return changes


def upsert_invoice(
    subscription: Subscription,
    payment: GatewayPayment,
    *,
    gateway_name: str,
    kind: str | None = None,
    plan: Plan | None = None,
    cycle: str | None = None,
) -> tuple[Invoice, str | None]:
    invoice = (
        Invoice.objects.select_for_update()
        .filter(gateway=gateway_name, gateway_id=payment.id)
        .first()
    )
    previous = invoice.status if invoice else None
    if invoice is None:
        invoice = Invoice(
            subscription=subscription,
            gateway=gateway_name,
            gateway_id=payment.id,
            kind=kind
            or (
                InvoiceKindChoices.RECURRING
                if payment.subscription_id
                else InvoiceKindChoices.PRORATION
            ),
            plan=plan or subscription.pending_plan or subscription.plan,
            cycle=cycle
            or subscription.pending_cycle
            or subscription.cycle
            or BillingCycleChoices.MONTHLY,
        )
    invoice.amount = payment.value
    invoice.status = payment.status
    invoice.issued_at = invoice.issued_at or payment.issued_at
    invoice.due_date = payment.due_date
    invoice.paid_at = payment.paid_at
    invoice.payment_url = payment.invoice_url
    invoice.save()
    return invoice, previous


def _cancel_open_invoices(
    subscription: Subscription, *, due_from: date | None = None
) -> None:
    invoices = Invoice.objects.open().filter(
        subscription=subscription, kind=InvoiceKindChoices.RECURRING
    )
    if due_from is not None:
        invoices = invoices.filter(due_date__gte=due_from)
    invoices.update(status=InvoiceStatusChoices.CANCELED, updated_at=timezone.now())


def _queue_email(email_class: str, subscription: Subscription, **kwargs) -> None:
    emails.queue_billing_email(email_class, subscription.organization, **kwargs)


@transaction.atomic
def upsert_profile(
    organization: Organization, data: dict, *, request=None, actor_member=None
) -> BillingProfile:
    subscription = locked_subscription(organization)
    profile = billing_profile(organization) or BillingProfile(organization=organization)
    changed = [
        name
        for name in PROFILE_FIELDS
        if getattr(profile, name, None) != data.get(name, '')
    ]
    for name in PROFILE_FIELDS:
        setattr(profile, name, data.get(name, ''))
    profile.full_clean(exclude=['organization'])
    profile.save()
    if subscription.gateway_customer_id and changed:
        gateway = get_gateway()
        _gateway_call(
            lambda: gateway.upsert_customer(
                _customer_data(profile, subscription), subscription.gateway_customer_id
            )
        )
    if changed:
        _record(
            AuditActionChoices.BILLING_PROFILE_UPDATED,
            subscription,
            request=request,
            actor_member=actor_member,
            metadata={'fields': changed},
        )
    return profile


def preview_change(
    subscription: Subscription, plan: Plan, cycle: str, now: datetime | None = None
) -> ChangePreview:
    now = now or timezone.now()
    kind = pricing.classify(subscription, plan, cycle)
    recurring = pricing.required_price(plan, cycle)
    if kind == ChangeKindChoices.NEW:
        profile = billing_profile(subscription.organization)
        return ChangePreview(
            kind=kind,
            charged_now=recurring,
            recurring_amount=recurring,
            recurring_from=pricing.period_end(now, cycle).date(),
            effective_at=now,
            requires_billing_profile=profile is None or not profile.is_complete,
        )
    if kind == ChangeKindChoices.DOWNGRADE:
        return ChangePreview(
            kind=kind,
            charged_now=Decimal('0.00'),
            recurring_amount=recurring,
            recurring_from=subscription.paid_period_end().date(),
            effective_at=subscription.paid_period_end(),
            requires_billing_profile=False,
        )
    charged = pricing.proration(subscription, plan, cycle, now)
    if charged < settings.BILLING_MIN_CHARGE:
        charged = Decimal('0.00')
    recurring_from = (
        subscription.paid_period_end().date()
        if cycle == subscription.cycle
        else pricing.period_end(now, cycle).date()
    )
    return ChangePreview(
        kind=kind,
        charged_now=charged,
        recurring_amount=recurring,
        recurring_from=recurring_from,
        effective_at=now,
        requires_billing_profile=False,
    )


def _create_gateway_subscription(
    gateway, subscription: Subscription, plan: Plan, cycle: str, next_due: date
) -> str:
    return _gateway_call(
        lambda: gateway.create_subscription(
            customer_id=subscription.gateway_customer_id,
            value=pricing.required_price(plan, cycle),
            cycle=cycle,
            next_due_date=next_due,
            description=_description(plan, cycle),
            external_reference=reference(subscription),
        )
    )


def _start_new(gateway, subscription: Subscription, plan: Plan, cycle: str) -> str:
    profile = billing_profile(subscription.organization)
    if profile is None or not profile.is_complete:
        raise BillingProfileRequiredError()
    _ensure_customer(gateway, subscription, profile)
    gateway_subscription_id = _create_gateway_subscription(
        gateway, subscription, plan, cycle, timezone.localdate()
    )
    payments = _gateway_call(
        lambda: gateway.list_subscription_payments(gateway_subscription_id)
    )
    first = min(
        (p for p in payments if p.status == InvoiceStatusChoices.PENDING),
        key=lambda p: p.due_date,
        default=None,
    )
    if first is None:
        raise GatewayUnavailableError()
    subscription.gateway_subscription_id = gateway_subscription_id
    subscription.pending_plan = plan
    subscription.pending_cycle = cycle
    subscription.save()
    upsert_invoice(
        subscription,
        first,
        gateway_name=gateway.name,
        kind=InvoiceKindChoices.RECURRING,
        plan=plan,
        cycle=cycle,
    )
    return first.invoice_url


def _cancel_stale_charges(gateway, subscription: Subscription, before: date) -> None:
    payments = _gateway_call(
        lambda: gateway.list_subscription_payments(subscription.gateway_subscription_id)
    )
    for payment in payments:
        if payment.status == InvoiceStatusChoices.PENDING and payment.due_date < before:
            _gateway_call(lambda p=payment: gateway.cancel_payment(p.id))
            Invoice.objects.filter(gateway=gateway.name, gateway_id=payment.id).update(
                status=InvoiceStatusChoices.CANCELED, updated_at=timezone.now()
            )


def _upgrade(
    gateway,
    subscription: Subscription,
    plan: Plan,
    cycle: str,
    now: datetime,
    *,
    request,
    actor_member,
) -> str | None:
    amount = pricing.proration(subscription, plan, cycle, now)
    before_plan, before_cycle = subscription.plan, subscription.cycle
    if cycle != subscription.cycle:
        subscription.current_period_start = now
        subscription.current_period_end = pricing.period_end(now, cycle)
    next_due = subscription.paid_period_end().date()
    _gateway_call(
        lambda: gateway.update_subscription(
            subscription.gateway_subscription_id,
            value=pricing.required_price(plan, cycle),
            cycle=cycle,
            next_due_date=next_due,
        )
    )
    if cycle != before_cycle:
        _cancel_stale_charges(gateway, subscription, next_due)
    payment_url = None
    if amount >= settings.BILLING_MIN_CHARGE:
        payment = _gateway_call(
            lambda: gateway.create_payment(
                customer_id=subscription.gateway_customer_id,
                value=amount,
                due_date=timezone.localdate(),
                description=str(_('Plan change adjustment')),
                external_reference=reference(subscription),
            )
        )
        upsert_invoice(
            subscription,
            payment,
            gateway_name=gateway.name,
            kind=InvoiceKindChoices.PRORATION,
            plan=plan,
            cycle=cycle,
        )
        payment_url = payment.invoice_url
    subscription.plan = plan
    subscription.cycle = cycle
    subscription.scheduled_plan = None
    subscription.scheduled_cycle = None
    subscription.save()
    _record(
        AuditActionChoices.BILLING_SUBSCRIPTION_PLAN_CHANGED,
        subscription,
        request=request,
        actor_member=actor_member,
        changes=_plan_changes(before_plan, before_cycle, plan, cycle),
        metadata={'reason': 'upgrade', 'charged_now': str(amount)},
    )
    _queue_email('PlanChangedEmail', subscription, plan_name=plan.name)
    return payment_url


def _downgrade(
    gateway,
    subscription: Subscription,
    plan: Plan,
    cycle: str,
    *,
    request,
    actor_member,
) -> None:
    _gateway_call(
        lambda: gateway.update_subscription(
            subscription.gateway_subscription_id,
            value=pricing.required_price(plan, cycle),
            cycle=cycle,
            next_due_date=subscription.paid_period_end().date(),
        )
    )
    subscription.scheduled_plan = plan
    subscription.scheduled_cycle = cycle
    subscription.save()
    _record(
        AuditActionChoices.BILLING_SUBSCRIPTION_CHANGE_SCHEDULED,
        subscription,
        request=request,
        actor_member=actor_member,
        changes=_plan_changes(subscription.plan, subscription.cycle, plan, cycle),
        metadata={'effective_at': subscription.paid_period_end().isoformat()},
    )


def _restore_gateway_subscription(gateway, subscription: Subscription) -> None:
    subscription.gateway_subscription_id = _create_gateway_subscription(
        gateway,
        subscription,
        subscription.plan,
        subscription.paid_cycle(),
        subscription.paid_period_end().date(),
    )
    subscription.cancel_at_period_end = False


@transaction.atomic
def change_plan(
    organization: Organization,
    plan: Plan,
    cycle: str,
    *,
    request=None,
    actor_member=None,
) -> tuple[Subscription, str | None]:
    subscription = locked_subscription(organization)
    if subscription.has_pending_change:
        raise InvalidState(_('A plan change is waiting for payment.'))
    kind = pricing.classify(subscription, plan, cycle)
    gateway = get_gateway()
    now = timezone.now()
    if kind == ChangeKindChoices.NEW:
        return subscription, _start_new(gateway, subscription, plan, cycle)
    if subscription.cancel_at_period_end:
        _restore_gateway_subscription(gateway, subscription)
        _record(
            AuditActionChoices.BILLING_SUBSCRIPTION_RESUMED,
            subscription,
            request=request,
            actor_member=actor_member,
        )
    if kind == ChangeKindChoices.UPGRADE:
        payment_url = _upgrade(
            gateway,
            subscription,
            plan,
            cycle,
            now,
            request=request,
            actor_member=actor_member,
        )
        return subscription, payment_url
    _downgrade(
        gateway, subscription, plan, cycle, request=request, actor_member=actor_member
    )
    return subscription, None


@transaction.atomic
def cancel(
    organization: Organization, *, request=None, actor_member=None
) -> Subscription:
    subscription = locked_subscription(organization)
    if not subscription.is_paid:
        raise ValidationError(_('There is no paid subscription to cancel.'))
    if subscription.cancel_at_period_end:
        raise ValidationError(_('The cancellation is already scheduled.'))
    gateway = get_gateway()
    if subscription.gateway_subscription_id:
        _gateway_call(
            lambda: gateway.delete_subscription(subscription.gateway_subscription_id)
        )
    _cancel_open_invoices(subscription, due_from=subscription.paid_period_end().date())
    subscription.gateway_subscription_id = ''
    subscription.cancel_at_period_end = True
    subscription.scheduled_plan = None
    subscription.scheduled_cycle = None
    subscription.save()
    _record(
        AuditActionChoices.BILLING_SUBSCRIPTION_CANCEL_SCHEDULED,
        subscription,
        request=request,
        actor_member=actor_member,
        metadata={'effective_at': subscription.paid_period_end().isoformat()},
    )
    _queue_email(
        'CancellationScheduledEmail',
        subscription,
        plan_name=subscription.plan.name,
        ends_on=subscription.paid_period_end().date().isoformat(),
    )
    return subscription


@transaction.atomic
def resume(
    organization: Organization, *, request=None, actor_member=None
) -> Subscription:
    subscription = locked_subscription(organization)
    gateway = get_gateway()
    if subscription.cancel_at_period_end:
        _restore_gateway_subscription(gateway, subscription)
        subscription.save()
        _record(
            AuditActionChoices.BILLING_SUBSCRIPTION_RESUMED,
            subscription,
            request=request,
            actor_member=actor_member,
        )
        return subscription
    if subscription.scheduled_plan_id is not None:
        _gateway_call(
            lambda: gateway.update_subscription(
                subscription.gateway_subscription_id,
                value=pricing.required_price(
                    subscription.plan, subscription.paid_cycle()
                ),
                cycle=subscription.paid_cycle(),
                next_due_date=subscription.paid_period_end().date(),
            )
        )
        scheduled_plan = subscription.scheduled_plan
        if scheduled_plan is None:
            raise ValueError('Scheduled plan is missing.')
        changes = _plan_changes(
            scheduled_plan,
            subscription.scheduled_cycle,
            subscription.plan,
            subscription.cycle,
        )
        subscription.scheduled_plan = None
        subscription.scheduled_cycle = None
        subscription.save()
        _record(
            AuditActionChoices.BILLING_SUBSCRIPTION_CHANGE_CANCELED,
            subscription,
            request=request,
            actor_member=actor_member,
            changes=changes,
        )
        return subscription
    raise ValidationError(_('Nothing is scheduled.'))


@transaction.atomic
def discard_change(
    organization: Organization, *, request=None, actor_member=None
) -> Subscription:
    subscription = locked_subscription(organization)
    if not subscription.has_pending_change:
        raise ValidationError(_('No plan change is waiting for payment.'))
    gateway = get_gateway()
    if subscription.gateway_subscription_id:
        _gateway_call(
            lambda: gateway.delete_subscription(subscription.gateway_subscription_id)
        )
    _cancel_open_invoices(subscription)
    pending_plan = subscription.pending_plan
    if pending_plan is None:
        raise ValueError('Pending plan is missing.')
    subscription.gateway_subscription_id = ''
    subscription.pending_plan = None
    subscription.pending_cycle = None
    subscription.save()
    _record(
        AuditActionChoices.BILLING_SUBSCRIPTION_CHANGE_CANCELED,
        subscription,
        request=request,
        actor_member=actor_member,
        metadata={'discarded_plan': pending_plan.code},
    )
    return subscription


def _find_subscription(payment: GatewayPayment, gateway_name: str) -> Subscription:
    invoice = (
        Invoice.objects.filter(gateway=gateway_name, gateway_id=payment.id)
        .values_list('subscription_id', flat=True)
        .first()
    )
    if invoice is not None:
        return Subscription.objects.get(pk=invoice)
    if payment.subscription_id:
        match = Subscription.objects.filter(
            gateway_subscription_id=payment.subscription_id
        ).first()
        if match is not None:
            return match
    subscription_id = subscription_id_from_reference(payment.external_reference)
    if subscription_id is not None:
        match = Subscription.objects.filter(pk=subscription_id).first()
        if match is not None:
            return match
    raise UnknownGatewayPayment(payment.id)


def _activate(subscription: Subscription, invoice: Invoice) -> None:
    before_plan, before_cycle = subscription.plan, subscription.cycle
    start = invoice.paid_at or timezone.now()
    pending_plan, pending_cycle = subscription.pending_plan, subscription.pending_cycle
    if pending_plan is None or pending_cycle is None:
        raise ValueError('The pending change is incomplete.')
    subscription.plan = pending_plan
    subscription.cycle = pending_cycle
    subscription.status = SubscriptionStatusChoices.ACTIVE
    subscription.current_period_start = start
    subscription.current_period_end = pricing.period_end(start, pending_cycle)
    subscription.trial_ends_at = None
    subscription.trial_reminder_sent = None
    subscription.courtesy = ''
    subscription.cancel_at_period_end = False
    subscription.pending_plan = None
    subscription.pending_cycle = None
    subscription.save()
    invoice.period_start = subscription.current_period_start
    invoice.period_end = subscription.current_period_end
    invoice.save(update_fields=['period_start', 'period_end', 'updated_at'])
    _record(
        AuditActionChoices.BILLING_SUBSCRIPTION_ACTIVATED,
        subscription,
        system=True,
        changes=_plan_changes(
            before_plan, before_cycle, subscription.plan, subscription.cycle
        ),
    )


@transaction.atomic
def sync_invoice(payment_id: str) -> Invoice | None:
    gateway = get_gateway()
    payment = gateway.get_payment(payment_id)
    if payment is None:
        return None
    subscription = _find_subscription(payment, gateway.name)
    subscription = (
        Subscription.objects.select_for_update(of=('self',))
        .select_related('plan', 'organization', 'pending_plan')
        .get(pk=subscription.pk)
    )
    invoice, previous = upsert_invoice(subscription, payment, gateway_name=gateway.name)
    if previous == invoice.status:
        return invoice
    if invoice.status == InvoiceStatusChoices.PAID:
        if (
            subscription.has_pending_change
            and invoice.kind == InvoiceKindChoices.RECURRING
            and payment.subscription_id == subscription.gateway_subscription_id
        ):
            _activate(subscription, invoice)
        _record(
            AuditActionChoices.BILLING_INVOICE_PAID,
            subscription,
            system=True,
            metadata={'invoice': invoice.pk, 'amount': str(invoice.amount)},
        )
        _queue_email(
            'PaymentConfirmedEmail',
            subscription,
            plan_name=subscription.plan.name,
            amount=str(invoice.amount),
        )
    elif invoice.status == InvoiceStatusChoices.REFUNDED:
        _record(
            AuditActionChoices.BILLING_INVOICE_REFUNDED,
            subscription,
            system=True,
            metadata={'invoice': invoice.pk, 'amount': str(invoice.amount)},
        )
    return invoice


@transaction.atomic
def end_trial(subscription_id: int, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    subscription = (
        Subscription.objects.select_for_update(of=('self',))
        .select_related('plan', 'organization')
        .get(pk=subscription_id)
    )
    if (
        subscription.status != SubscriptionStatusChoices.TRIALING
        or subscription.trial_ends_at is None
        or subscription.trial_ends_at > now
    ):
        return False
    before = subscription.plan
    free = Plan.objects.free()
    subscription.plan = free
    subscription.status = SubscriptionStatusChoices.ACTIVE
    subscription.trial_ends_at = None
    subscription.trial_reminder_sent = None
    subscription.courtesy = ''
    subscription.save()
    _record(
        AuditActionChoices.BILLING_SUBSCRIPTION_PLAN_CHANGED,
        subscription,
        system=True,
        changes=_plan_changes(before, None, free, None),
        metadata={'reason': 'trial_ended'},
    )
    return True


@transaction.atomic
def apply_period_end(subscription_id: int, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    subscription = (
        Subscription.objects.select_for_update(of=('self',))
        .select_related('plan', 'organization', 'scheduled_plan')
        .get(pk=subscription_id)
    )
    if not subscription.is_paid or subscription.paid_period_end() > now:
        return False
    if subscription.cancel_at_period_end:
        before_plan, before_cycle = subscription.plan, subscription.cycle
        free = Plan.objects.free()
        subscription.plan = free
        subscription.cycle = None
        subscription.current_period_start = None
        subscription.current_period_end = None
        subscription.cancel_at_period_end = False
        subscription.save()
        _record(
            AuditActionChoices.BILLING_SUBSCRIPTION_CANCELED,
            subscription,
            system=True,
            changes=_plan_changes(before_plan, before_cycle, free, None),
        )
        _queue_email(
            'SubscriptionCanceledEmail', subscription, plan_name=before_plan.name
        )
        return True
    start = subscription.paid_period_end()
    if subscription.scheduled_plan_id is not None:
        before_plan, before_cycle = subscription.plan, subscription.cycle
        scheduled_plan = subscription.scheduled_plan
        if scheduled_plan is None:
            raise ValueError('Scheduled plan is missing.')
        subscription.plan = scheduled_plan
        subscription.cycle = subscription.scheduled_cycle
        subscription.scheduled_plan = None
        subscription.scheduled_cycle = None
        _record(
            AuditActionChoices.BILLING_SUBSCRIPTION_PLAN_CHANGED,
            subscription,
            system=True,
            changes=_plan_changes(
                before_plan, before_cycle, subscription.plan, subscription.cycle
            ),
            metadata={'reason': 'scheduled'},
        )
        _queue_email('PlanChangedEmail', subscription, plan_name=subscription.plan.name)
    cycle = subscription.paid_cycle()
    period_start = start
    period_end = pricing.period_end(period_start, cycle)
    while period_end <= now:
        period_start, period_end = period_end, pricing.period_end(period_end, cycle)
    subscription.current_period_start = period_start
    subscription.current_period_end = period_end
    subscription.save()
    return True


def days_left(trial_ends_at: datetime, now: datetime) -> int:
    return math.ceil((trial_ends_at - now) / timedelta(days=1))


@transaction.atomic
def send_trial_reminder(subscription_id: int, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    subscription = (
        Subscription.objects.select_for_update(of=('self',))
        .select_related('plan', 'organization')
        .get(pk=subscription_id)
    )
    if (
        subscription.status != SubscriptionStatusChoices.TRIALING
        or subscription.trial_ends_at is None
    ):
        return False
    left = days_left(subscription.trial_ends_at, now)
    marks = sorted(day for day in settings.BILLING_TRIAL_REMINDER_DAYS if day >= left)
    if left <= 0 or not marks:
        return False
    mark = marks[0]
    if (
        subscription.trial_reminder_sent is not None
        and subscription.trial_reminder_sent <= mark
    ):
        return False
    subscription.trial_reminder_sent = mark
    subscription.save(update_fields=['trial_reminder_sent', 'updated_at'])
    _queue_email(
        'TrialEndingEmail',
        subscription,
        plan_name=subscription.plan.name,
        days=left,
        ends_on=subscription.trial_ends_at.date().isoformat(),
    )
    return True
