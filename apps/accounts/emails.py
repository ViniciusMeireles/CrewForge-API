from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _

from apps.accounts.choices import OrganizationImageTypeChoices
from apps.generics.mails.bases import CTAEmail, EmailBase

if TYPE_CHECKING:
    from apps.accounts.models.invitation import Invitation
    from apps.accounts.models.organization import Organization


class PasswordResetRequestEmail(EmailBase):
    template_name = 'accounts/emails/base.html'

    subject = _('Password Reset')
    preheader = _('Use the link below to reset your password.')
    title = _('Password Reset Request')
    content = _(
        'We received a request to reset your password. Click the button below to set '
        'a new password. If you did not request this, please ignore this email.'
    )

    def __init__(self, *, reset_url: str, **kwargs):
        super().__init__(**kwargs)
        self.cta = CTAEmail(url=reset_url, text=_('Reset Password'))

    @classmethod
    def get_preview_kwargs(cls, **kwargs) -> dict:
        kwargs = super().get_preview_kwargs(**kwargs)
        kwargs.update(
            {
                'reset_url': f'{settings.FRONTEND_RESET_URL}?uid=abc123&token=def456',
            }
        )
        return kwargs


class EmailVerificationEmail(EmailBase):
    template_name = 'accounts/emails/base.html'

    subject = _('Verify your email')
    preheader = _('Confirm your email address to finish setting up your account.')
    title = _('Verify your email address')
    content = _(
        'Click the button below to confirm that this email address is yours. '
        'Invitations sent to it will only appear after you confirm. If you did not '
        'create an account, please ignore this email.'
    )

    def __init__(self, *, verify_url: str, **kwargs):
        super().__init__(**kwargs)
        self.cta = CTAEmail(url=verify_url, text=_('Verify Email'))

    @classmethod
    def get_preview_kwargs(cls, **kwargs) -> dict:
        kwargs = super().get_preview_kwargs(**kwargs)
        kwargs.update(
            {
                'verify_url': (
                    f'{settings.FRONTEND_VERIFY_EMAIL_URL}?uid=abc123&token=def456'
                ),
            }
        )
        return kwargs


class InvitationEmail(EmailBase):
    template_name = 'accounts/emails/base.html'

    subject = _('You have been invited to join {organization_name}')
    preheader = _('Click the button below to accept the invitation.')
    title = _('Invitation to join {organization_name}')
    content = _(
        'You have been invited to join <strong>{organization_name}</strong>. '
        'Click the button below to accept the invitation and get started.'
    )

    def __init__(self, *, invitation: Invitation | int, **kwargs):
        super().__init__(**kwargs)
        if isinstance(invitation, int):
            from apps.accounts.models.invitation import Invitation

            invitation = Invitation.objects.get(id=invitation)
        self._obj = invitation

    def get_object(self) -> Invitation:
        return self._obj

    def get_organization(self) -> Organization:
        return self.get_object().organization

    def get_organization_name(self) -> str:
        return self.get_organization().name

    def get_subject(self) -> str:
        return self.subject.format(organization_name=self.get_organization_name())

    def get_recipient_list(self) -> list[str]:
        return [self.get_object().email]

    def get_title(self) -> str:
        return self.title.format(organization_name=self.get_organization_name())

    def get_content(self) -> str:
        return self.content.format(organization_name=self.get_organization_name())

    def get_cta(self) -> CTAEmail:
        return CTAEmail(
            url=self.get_object().get_invitation_link() if not self.is_preview else '',
            text=_('Accept Invitation'),
        )

    def get_logo(self) -> str:
        if not (profile := self.get_organization().get_profile()):
            return ''
        logo_image = (
            profile.images.filter(
                image_type=OrganizationImageTypeChoices.LOGO, is_active=True
            )
            .select_related('image')
            .first()
        )
        if logo_image and logo_image.image:
            return logo_image.image.to_base64() or ''
        return ''

    def send(self, fail_silently: bool = False) -> int:
        if send := super().send(fail_silently=fail_silently):
            instance = self.get_object()
            instance.last_email_sent_at = timezone.now()
            instance.save(update_fields=['last_email_sent_at', 'updated_at'])
        return send

    @classmethod
    def get_preview_kwargs(cls, **kwargs) -> dict:
        kwargs = super().get_preview_kwargs(**kwargs)
        kwargs.update(
            {
                'invitation': None,
            }
        )
        return kwargs


class OrganizationNoticeEmail(EmailBase):
    """
    Notice about an Organization sent to its Owners by platform staff actions.

    Built from plain names so the Celery task can rebuild it; the internal reason
    of the action is never part of it (BR-16, BR-19).
    """

    template_name = 'accounts/emails/base.html'

    def __init__(self, *, organization_name: str, new_owner_name: str = '', **kwargs):
        super().__init__(**kwargs)
        self.organization_name = organization_name
        self.new_owner_name = new_owner_name

    def _format(self, text, escape_names: bool = False) -> str:
        names = {
            'organization': self.organization_name,
            'new_owner': self.new_owner_name,
        }
        if escape_names:
            names = {key: escape(value) for key, value in names.items()}
        return str(text).format(system=self.get_system_title(), **names)

    def get_subject(self) -> str:
        return self._format(self.subject)

    def get_title(self) -> str:
        return self._format(self.subject)

    def get_content(self) -> str:
        return self._format(self.content, escape_names=True)

    @classmethod
    def get_preview_kwargs(cls, **kwargs) -> dict:
        kwargs = super().get_preview_kwargs(**kwargs)
        kwargs.update(
            {'organization_name': 'Acme Inc', 'new_owner_name': 'Maria Silva'}
        )
        return kwargs


class OrganizationSuspendedEmail(OrganizationNoticeEmail):
    subject = _('Your organization {organization} was suspended')
    content = _(
        'Your organization {organization} was suspended by {system}. Its members '
        "can't access it until it is reactivated. If you have questions, contact "
        'support.'
    )


class OrganizationReactivatedEmail(OrganizationNoticeEmail):
    subject = _('Your organization {organization} is active again')
    content = _(
        'Your organization {organization} was reactivated. Its members can access it '
        'again.'
    )


class OwnershipTransferredNewOwnerEmail(OrganizationNoticeEmail):
    subject = _('You are now the owner of {organization}')
    content = _('{system} transferred the ownership of {organization} to you.')


class OwnershipTransferredPreviousOwnerEmail(OrganizationNoticeEmail):
    subject = _('Ownership of {organization} was transferred')
    content = _(
        '{system} transferred the ownership of {organization} to {new_owner}. You '
        'remain a member as an admin.'
    )
