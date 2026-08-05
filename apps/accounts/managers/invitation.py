from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from apps.generics.managers.querysets import BaseManager, BaseQuerySet

User = get_user_model()


class InvitationQuerySet(BaseQuerySet):
    def filter_received_by_user(self, user: User):
        return self.filter(
            Q(email=user.email, member__isnull=True) | Q(member__user=user),
        )

    def filter_acceptable(self):
        return (
            self.exclude(
                is_accepted=True,
            )
            .exclude(
                is_declined=True,
            )
            .exclude(
                is_expired=True,
            )
            .exclude(
                is_active=False,
            )
            .exclude(
                expired_at__lt=timezone.now(),
            )
            .exclude(
                member__isnull=False,
            )
        )


InvitationManager = BaseManager.from_queryset(InvitationQuerySet)
