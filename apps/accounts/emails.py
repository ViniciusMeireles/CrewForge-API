from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

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
