from datetime import date

from django.conf import settings
from django.utils import formats
from django.utils.functional import Promise
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _

from apps.accounts.utils.language import resolve_recipient_language
from apps.generics.mails.bases import CTAEmail, EmailBase
from apps.generics.utils.db import queue_on_commit


def billing_url() -> str:
    base = (settings.FRONTEND_URL or '').rstrip('/')
    return f'{base}/management/billing'


class BillingEmail(EmailBase):
    """Billing notice sent to the billing email and the Owner (BR-30)."""

    template_name = 'accounts/emails/base.html'
    subject_template: str | Promise = ''
    content_template: str | Promise = ''

    def __init__(
        self,
        *,
        organization_name: str,
        plan_name: str = '',
        amount: str = '',
        ends_on: str = '',
        days: int = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.organization_name = organization_name
        self.plan_name = plan_name
        self.amount = amount
        self.ends_on = ends_on
        self.days = days
        self.cta = CTAEmail(url=billing_url(), text=str(_('Open plan and billing')))

    def _format(self, text: str | Promise, escape_names: bool = False) -> str:
        ends_on = (
            formats.date_format(date.fromisoformat(self.ends_on), 'DATE_FORMAT')
            if self.ends_on
            else ''
        )
        names = {
            'organization': self.organization_name,
            'plan': self.plan_name,
            'amount': f'R$ {self.amount}' if self.amount else '',
            'date': ends_on,
            'days': self.days,
        }
        if escape_names:
            names = {
                key: escape(value) if isinstance(value, str) else value
                for key, value in names.items()
            }
        return str(text).format(**names)

    def get_subject(self) -> str:
        return self._format(self.subject_template)

    def get_title(self) -> str:
        return self._format(self.subject_template)

    def get_content(self) -> str:
        return self._format(self.content_template, escape_names=True)

    @classmethod
    def get_preview_kwargs(cls, view=None) -> dict:
        kwargs = super().get_preview_kwargs(view=view)
        kwargs.update(
            {
                'organization_name': 'Acme Inc',
                'plan_name': 'Pro',
                'amount': '99.00',
                'ends_on': '2026-12-24',
                'days': 3,
            }
        )
        return kwargs


class TrialEndingEmail(BillingEmail):
    subject_template = _('The trial of {organization} ends on {date}')
    content_template = _(
        'The {plan} trial of {organization} ends on {date}. Choose a paid plan to keep '
        'its limits and features; otherwise it moves to the Free plan. Your data is '
        'kept.'
    )


class PaymentConfirmedEmail(BillingEmail):
    subject_template = _('Payment confirmed for {organization}')
    content_template = _(
        'We received the payment of {amount} for {organization}. Its {plan} plan is '
        'active.'
    )


class PlanChangedEmail(BillingEmail):
    subject_template = _('The plan of {organization} changed')
    content_template = _('{organization} is now on the {plan} plan.')


class CancellationScheduledEmail(BillingEmail):
    subject_template = _('The subscription of {organization} will end')
    content_template = _(
        'The {plan} subscription of {organization} ends on {date}. Then it moves to '
        'the Free plan and its limits. Your data is kept. You can resume the '
        'subscription until then.'
    )


class SubscriptionCanceledEmail(BillingEmail):
    subject_template = _('The subscription of {organization} ended')
    content_template = _(
        '{organization} moved to the Free plan. Your data is kept. You can choose a '
        'paid plan again at any time.'
    )


def recipients(organization) -> list[tuple[str, str]]:
    from apps.billing.models.billing_profile import BillingProfile

    found: list[tuple[str, str]] = []
    owner = organization.owner
    if owner is not None and owner.user.email:
        found.append((owner.user.email, resolve_recipient_language(owner.user)))
    profile = BillingProfile.objects.filter(organization=organization).first()
    if profile is not None and profile.email:
        language = found[0][1] if found else resolve_recipient_language()
        if profile.email.lower() not in {email.lower() for email, _ in found}:
            found.append((profile.email, language))
    return found


def queue_billing_email(email_class_name: str, organization, **kwargs) -> None:
    from apps.generics.tasks import send_email

    for email, language in recipients(organization):
        queue_on_commit(
            lambda email=email, language=language: send_email.apply_async(
                kwargs={
                    'email_class_path': f'apps.billing.emails.{email_class_name}',
                    'recipient_list': [email],
                    'kwargs': {'organization_name': organization.name, **kwargs},
                    'language': language,
                },
                countdown=1,
            ),
            f'{email_class_name} for organization {organization.pk}',
        )
