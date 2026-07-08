import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.choices import InvitationErrorMessages, MemberRoleChoices
from apps.accounts.consts import INVITATION_ACCEPT_URL_PATH
from apps.accounts.managers.invitation import InvitationManager
from apps.generics.models.abstracts import BaseModel
from apps.generics.utils.shortcuts import get_object_or_none


class Invitation(BaseModel):
    email = models.EmailField(
        verbose_name=_('Email'),
        help_text=_('Email of the user to invite'),
        null=False,
        blank=False,
    )
    is_accepted = models.BooleanField(
        default=False,
        verbose_name=_('Is Accepted'),
        help_text=_('Is the invitation accepted by the user'),
    )
    is_expired = models.BooleanField(
        default=False,
        verbose_name=_('Is Expired'),
        help_text=_('Is the invitation expired'),
    )
    expired_at = models.DateTimeField(
        verbose_name=_('Expired At'),
        help_text=_('Date and time when the invitation will expire'),
        null=True,
        blank=True,
    )
    role = models.CharField(
        max_length=20,
        choices=MemberRoleChoices.choices,
        default=MemberRoleChoices.MEMBER,
        verbose_name=_('Role'),
        help_text=_('User role in the organization'),
    )
    organization = models.ForeignKey(
        to='accounts.Organization',
        on_delete=models.CASCADE,
        related_name='invitations',
        verbose_name=_('Organization'),
        help_text=_('Organization to which the user is invited'),
        null=False,
        blank=False,
    )
    key = models.UUIDField(
        verbose_name=_('Key'),
        help_text=_('Key for the invitation'),
    )
    member = models.OneToOneField(
        to='accounts.Member',
        on_delete=models.CASCADE,
        verbose_name=_('Member'),
        help_text=_('Member associated with the invitation'),
        null=True,
        blank=True,
    )
    last_email_sent_at = models.DateTimeField(
        verbose_name=_('Last Email Sent At'),
        help_text=_('Date and time when the last invitation email was sent'),
        null=True,
        blank=True,
    )

    objects = InvitationManager()

    class Meta:
        ordering = ['-id']
        verbose_name = _('Invitation')
        verbose_name_plural = _('Invitations')

    def __str__(self):
        return self.email

    def get_user(self):
        """Get the user associated with the invitation email."""
        return get_object_or_none(get_user_model(), email=self.email, is_active=True)

    def get_invitation_link(self) -> str:
        """Return the absolute URL for accepting the invitation."""
        return (
            f'{settings.FRONTEND_URL}/{INVITATION_ACCEPT_URL_PATH.format(key=self.key)}'
        )

    def is_acceptable(self) -> tuple[bool, str]:
        """
        Check if the invitation is acceptable or not.
        :return: Tuple of boolean and message.
        """
        if self.is_accepted:
            return False, str(InvitationErrorMessages.INVITATION_ACCEPTED.label)
        if self.is_expired:
            return False, str(InvitationErrorMessages.INVITATION_EXPIRED.label)
        elif self.expired_at and self.expired_at <= timezone.now():
            self.is_expired = True
            self.save()
            return False, str(InvitationErrorMessages.INVITATION_EXPIRED.label)
        elif (user := self.get_user()) and self.organization.members.filter(
            user=user
        ).exists():
            return False, str(InvitationErrorMessages.USER_ALREADY_MEMBER.label)
        return True, ''

    def accept(self, member, check: bool = True):
        """
        Accept the invitation.
        :param member: Member created with this invite.
        :param check: Whether to check if the invitation is acceptable or not.
        :return: Member object if the invitation is accepted, None otherwise.
        """
        if check:
            is_acceptable, message = self.is_acceptable()
            if not is_acceptable:
                raise ValueError(message)

        self.member = member
        self.is_accepted = True
        self.save()

    def clean(self):
        """
        Clean the invitation before saving it.
        :return: None
        """
        if self.expired_at and self.expired_at <= timezone.now():
            raise ValueError(_('Expired date must be greater than now'))

    def send_email(self) -> int:
        from apps.accounts.emails import InvitationEmail

        return InvitationEmail(invitation=self).send(fail_silently=False)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = uuid.uuid4()
            if (
                update_fields := kwargs.pop('update_fields', None)
            ) and 'key' not in update_fields:
                update_fields.append('key')
                kwargs['update_fields'] = update_fields
        return super().save(*args, **kwargs)
