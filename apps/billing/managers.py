from datetime import timedelta

from django.db import models
from django.db.models import F
from django.utils import timezone

from apps.generics.managers.querysets import BaseQuerySet


class PlanQuerySet(BaseQuerySet):
    def offered(self):
        return self.filter(is_active=True, is_public=True).order_by(
            'sort_order', F('monthly_price').asc(nulls_last=True), 'id'
        )

    def default(self):
        return self.get(is_default=True)

    def free(self):
        return self.get(is_free=True)


class SubscriptionQuerySet(BaseQuerySet):
    pass


class InvoiceQuerySet(BaseQuerySet):
    def open(self):
        return self.filter(status__in=('pending', 'overdue'))


class GatewayEventQuerySet(models.QuerySet):
    def unprocessed(self):
        return self.filter(processed_at__isnull=True)

    def older_than(self, days: int):
        return self.filter(received_at__lt=timezone.now() - timedelta(days=days))
