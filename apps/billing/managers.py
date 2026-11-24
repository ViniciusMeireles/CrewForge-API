from django.db.models import F

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
