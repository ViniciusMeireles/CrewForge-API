from functools import reduce
from operator import or_
from typing import Any

from django.db import models

from apps.audit.choices import ACCOUNT_ACTION_PREFIXES


class AuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RuntimeError('Audit events are immutable.')

    def delete(self):
        raise RuntimeError('Audit events are immutable.')

    def purge_organization_events(
        self, *, organization_ids, before, batch_size: int = 5000
    ) -> int:
        """The only deletion path: Organization events older than ``before``."""
        deleted = 0
        matching: models.QuerySet[Any] = models.QuerySet(
            self.model, using=self.db
        ).filter(
            organization_id__in=list(organization_ids),
            organization_id__isnull=False,
            created_at__lt=before,
        )
        while ids := list(matching.values_list('pk', flat=True)[:batch_size]):
            batch: models.QuerySet[Any] = models.QuerySet(
                self.model, using=self.db
            ).filter(pk__in=ids)
            deleted += batch._raw_delete(batch.db)
        return deleted

    def for_organization(self, organization_id: int | None) -> AuditEventQuerySet:
        return self.filter(organization_id=organization_id)

    def account_activity(self, user) -> AuditEventQuerySet:
        """Account events (no organization) that belong to ``user``."""
        actions = reduce(
            or_,
            (models.Q(action__startswith=prefix) for prefix in ACCOUNT_ACTION_PREFIXES),
        )
        return self.filter(actions, organization__isnull=True, subject_user=user)


AuditEventManager = models.Manager.from_queryset(AuditEventQuerySet)
