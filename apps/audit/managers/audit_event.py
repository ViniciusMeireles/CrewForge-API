from functools import reduce
from operator import or_

from django.db import models

from apps.audit.choices import ACCOUNT_ACTION_PREFIXES


class AuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RuntimeError('Audit events are immutable.')

    def delete(self):
        raise RuntimeError('Audit events are immutable.')

    def for_organization(self, organization_id: int | None) -> 'AuditEventQuerySet':
        return self.filter(organization_id=organization_id)

    def account_activity(self, user) -> 'AuditEventQuerySet':
        """Account events (no organization) that belong to ``user``."""
        actions = reduce(
            or_,
            (models.Q(action__startswith=prefix) for prefix in ACCOUNT_ACTION_PREFIXES),
        )
        return self.filter(actions, organization__isnull=True, subject_user=user)


AuditEventManager = models.Manager.from_queryset(AuditEventQuerySet)
