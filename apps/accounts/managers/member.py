from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.choices import InvitationErrorMessages, MemberErrorMessages
from apps.generics.managers.querysets import BaseManager, BaseQuerySet

if TYPE_CHECKING:
    from django.contrib.auth import get_user_model

    from apps.accounts.models.member import Member
    from apps.accounts.models.organization import Organization

    User = get_user_model()


class MemberQuerySet(BaseQuerySet):
    def filter_actives(self):
        return (
            super()
            .filter_actives()
            .filter(
                organization__is_active=True,
            )
        )

    def filter_inactives(self):
        return self.exclude(is_active=True).exclude(
            organization__is_active=True,
        )

    def admit(
        self,
        *,
        user: 'User',
        organization: 'Organization',
        role: str,
        nickname: str | None = None,
    ) -> tuple['Member', bool]:
        """
        Create the membership of ``user`` in ``organization``, or reactivate
        the removed one (readmission) with the given role and nickname.
        Returns the member and whether it was a readmission.
        """
        nickname = nickname or None
        with transaction.atomic():
            member = (
                self.select_for_update()
                .filter(user=user, organization=organization)
                .first()
            )
            if member is not None and member.is_active:
                raise ValueError(str(InvitationErrorMessages.USER_ALREADY_MEMBER.label))
            self._check_nickname(organization, nickname, member)
            if member is None:
                try:
                    with transaction.atomic():
                        member = self.create(
                            user=user,
                            organization=organization,
                            role=role,
                            nickname=nickname,
                        )
                except IntegrityError as exc:
                    if not self.filter(
                        user=user, organization=organization, is_active=True
                    ).exists():
                        raise
                    raise ValueError(
                        str(InvitationErrorMessages.USER_ALREADY_MEMBER.label)
                    ) from exc
                return member, False
            member.is_active = True
            member.role = role
            member.nickname = nickname
            member.joined_at = timezone.now()
            member.save(
                update_fields=[
                    'is_active',
                    'role',
                    'nickname',
                    'joined_at',
                    'updated_at',
                ],
            )
            return member, True

    def _check_nickname(self, organization, nickname, member) -> None:
        if nickname is None:
            return
        taken = self.filter(organization=organization, nickname=nickname)
        if member is not None:
            taken = taken.exclude(pk=member.pk)
        if taken.exists():
            raise ValidationError(
                {'nickname': [MemberErrorMessages.NICKNAME_TAKEN.label]},
            )


MemberManager = BaseManager.from_queryset(MemberQuerySet)
