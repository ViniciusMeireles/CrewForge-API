from typing import TYPE_CHECKING

from django.db.models import BooleanField, Exists, ExpressionWrapper, OuterRef, Q
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
            condition |= Q(email__iexact=user.email, member__isnull=True)
        return self.filter(condition, organization__is_active=True)

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
        return self.filter_pending().exclude_already_members()

    def filter_pending(self):
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
            .exclude(
                organization__is_active=False,
            )
        )

    def exclude_already_members(self):
        """
        Exclude invitations whose invitee is already an active member of the
        organization: the linked user, or the active user with the invitation
        email when no user is linked (same rule as Invitation.is_acceptable).
        A removed member can be readmitted, so inactive memberships are kept.
        """
        return self.exclude(self._invitee_membership_exists(is_active=True))

    def annotate_former_member(self):
        """
        Annotate ``is_former_member``: the invitee has a removed membership in
        the organization and no active one.
        """
        return self.annotate(
            is_former_member=ExpressionWrapper(
                self._invitee_membership_exists(is_active=False)
                & ~self._invitee_membership_exists(is_active=True),
                output_field=BooleanField(),
            ),
        )

    @staticmethod
    def _invitee_membership_exists(*, is_active: bool) -> Q:
        from apps.accounts.models.member import Member

        members = Member.objects.filter(
            organization_id=OuterRef('organization_id'),
            is_active=is_active,
        )
        linked_user = Exists(members.filter(user_id=OuterRef('user_id')))
        email_user = Exists(
            members.filter(user__email=OuterRef('email'), user__is_active=True),
        )
        return Q(linked_user) | (Q(user__isnull=True) & Q(email_user))


InvitationManager = BaseManager.from_queryset(InvitationQuerySet)
