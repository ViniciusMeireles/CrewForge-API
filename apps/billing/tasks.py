import logging
import time
from collections import defaultdict
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.audit.models.audit_event import AuditEvent
from apps.billing.entitlements import AUDIT_RETENTION_DAYS, value
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
