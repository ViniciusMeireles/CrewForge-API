import logging
import time
from collections import defaultdict
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.models.audit_event import AuditEvent
from apps.billing import payments
from apps.billing.choices import SubscriptionStatusChoices
from apps.billing.entitlements import AUDIT_RETENTION_DAYS, value
from apps.billing.exceptions import UnknownGatewayPayment
from apps.billing.gateways import get_gateway
from apps.billing.gateways.base import GatewayError
from apps.billing.models.gateway_event import GatewayEvent
from apps.billing.models.invoice import Invoice
from apps.billing.models.subscription import Subscription

logger = logging.getLogger(__name__)


def purge_audit_events_by_retention() -> int:
    groups: dict[int, list[int]] = defaultdict(list)
    for subscription in Subscription.objects.select_related('plan'):
        days = value(subscription.plan, AUDIT_RETENTION_DAYS)
        if days is not None:
            groups[days].append(subscription.organization_id)
    started = time.monotonic()
    now = timezone.now()
    deleted = 0
    for days, organization_ids in groups.items():
        deleted += AuditEvent.objects.purge_organization_events(
            organization_ids=organization_ids, before=now - timedelta(days=days)
        )
    logger.info(
        'billing.audit_purge',
        extra={
            'organizations': sum(len(ids) for ids in groups.values()),
            'deleted': deleted,
            'duration_ms': round((time.monotonic() - started) * 1000),
        },
    )
    return deleted


@shared_task(ignore_result=True)
def purge_audit_events():
    if not settings.AUDIT_RETENTION_PURGE_ENABLED:
        return 0
    return purge_audit_events_by_retention()


PAYMENT_EVENTS = frozenset(
    {
        'PAYMENT_CREATED',
        'PAYMENT_UPDATED',
        'PAYMENT_CONFIRMED',
        'PAYMENT_RECEIVED',
        'PAYMENT_OVERDUE',
        'PAYMENT_DELETED',
        'PAYMENT_RESTORED',
        'PAYMENT_REFUNDED',
        'PAYMENT_CHARGEBACK_REQUESTED',
    }
)
RECONCILE_WINDOW_DAYS = 40


@shared_task(
    bind=True,
    autoretry_for=(GatewayError,),
    retry_backoff=True,
    max_retries=5,
    ignore_result=True,
)
def process_gateway_event(self, event_pk: int):
    with transaction.atomic():
        event = GatewayEvent.objects.select_for_update().filter(pk=event_pk).first()
        if event is None or event.processed_at is not None:
            return
        event.attempts += 1
        event.save(update_fields=['attempts'])
    if event.event_type in PAYMENT_EVENTS and event.payment_id:
        try:
            payments.sync_invoice(event.payment_id)
        except UnknownGatewayPayment:
            GatewayEvent.objects.filter(pk=event_pk).update(
                error='unknown payment', processed_at=timezone.now()
            )
            logger.warning('billing.event_failed', extra={'event_id': event.event_id})
            return
        except GatewayError as error:
            GatewayEvent.objects.filter(pk=event_pk).update(error=str(error))
            logger.warning(
                'billing.event_failed',
                extra={'event_id': event.event_id, 'attempts': event.attempts},
            )
            raise
    GatewayEvent.objects.filter(pk=event_pk).update(
        processed_at=timezone.now(), error=''
    )


def reconcile() -> dict[str, int]:
    gateway = get_gateway()
    payment_ids = set(Invoice.objects.open().values_list('gateway_id', flat=True))
    since = timezone.localdate() - timedelta(days=RECONCILE_WINDOW_DAYS)
    for subscription_id in Subscription.objects.exclude(
        gateway_subscription_id=''
    ).values_list('gateway_subscription_id', flat=True):
        try:
            listed = gateway.list_subscription_payments(subscription_id)
        except GatewayError:
            logger.warning(
                'billing.reconcile_failed', extra={'subscription': subscription_id}
            )
            continue
        payment_ids.update(p.id for p in listed if p.due_date >= since)
    checked = changed = 0
    for payment_id in sorted(payment_ids):
        before = (
            Invoice.objects.filter(gateway=gateway.name, gateway_id=payment_id)
            .values_list('status', flat=True)
            .first()
        )
        try:
            invoice = payments.sync_invoice(payment_id)
        except GatewayError, UnknownGatewayPayment:
            logger.warning('billing.reconcile_failed', extra={'payment': payment_id})
            continue
        checked += 1
        if invoice is not None and invoice.status != before:
            changed += 1
    GatewayEvent.objects.older_than(settings.BILLING_EVENT_RETENTION_DAYS).delete()
    logger.info('billing.reconciled', extra={'checked': checked, 'changed': changed})
    return {'checked': checked, 'changed': changed}


@shared_task(ignore_result=True)
def reconcile_invoices():
    return reconcile()


@shared_task(ignore_result=True)
def apply_period_end():
    ids = Subscription.objects.filter(
        current_period_end__lte=timezone.now(), cycle__isnull=False
    ).values_list('pk', flat=True)
    return sum(payments.apply_period_end(pk) for pk in list(ids))


@shared_task(ignore_result=True)
def expire_trials():
    ids = Subscription.objects.filter(
        status=SubscriptionStatusChoices.TRIALING, trial_ends_at__lte=timezone.now()
    ).values_list('pk', flat=True)
    return sum(payments.end_trial(pk) for pk in list(ids))


@shared_task(ignore_result=True)
def send_trial_reminders():
    horizon = timezone.now() + timedelta(days=max(settings.BILLING_TRIAL_REMINDER_DAYS))
    ids = Subscription.objects.filter(
        status=SubscriptionStatusChoices.TRIALING,
        trial_ends_at__gt=timezone.now(),
        trial_ends_at__lte=horizon,
    ).values_list('pk', flat=True)
    return sum(payments.send_trial_reminder(pk) for pk in list(ids))
