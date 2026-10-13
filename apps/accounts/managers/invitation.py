from typing import TYPE_CHECKING

from django.db.models import Q
from django.utils import timezone

from apps.accounts.choices import MemberRoleChoices
from apps.generics.managers.querysets import BaseManager, BaseQuerySet

if TYPE_CHECKING:
    from django.contrib.auth import get_user_model

    from apps.accounts.models.member import Member

    User = get_user_model()


class InvitationQuerySet(BaseQuerySet):
    def filter_received_by_user(self, user: 'User'):
        condition = Q(member__user=user)
        if user.email_verified:
            condition |= Q(email=user.email, member__isnull=True)
        return self.filter(condition)

    def filter_visible_to(self, member: 'Member | None'):
        if member is None:
            return self.none()
        roles = []
        if member.has_admin_permission:
            roles.extend(
                [MemberRoleChoices.MANAGER, MemberRoleChoices.MEMBER],
            )
        if member.has_owner_permission:
            roles.extend(
                [MemberRoleChoices.OWNER, MemberRoleChoices.ADMIN],
            )
        return self.filter(role__in=roles)

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
                expired_at__lte=timezone.now(),
            )
            .exclude(
                member__isnull=False,
            )
        )


InvitationManager = BaseManager.from_queryset(InvitationQuerySet)
