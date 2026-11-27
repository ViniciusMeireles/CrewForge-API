from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import translation

from apps.accounts.factories.organizations import OrganizationFactory
from apps.billing import emails
from apps.billing.factories.payments import BillingProfileFactory

EMAILS = (
    'TrialEndingEmail',
    'PaymentConfirmedEmail',
    'PlanChangedEmail',
    'CancellationScheduledEmail',
    'SubscriptionCanceledEmail',
)
KWARGS = {
    'organization_name': 'Acme <b>Inc</b>',
    'plan_name': 'Pro',
    'amount': '99.00',
    'ends_on': '2026-12-24',
    'days': 3,
}


@override_settings(FRONTEND_URL='https://app.example.com')
class BillingEmailTestCase(TestCase):
    def test_each_email_renders_in_both_languages(self):
        for name in EMAILS:
            for language in ('en-us', 'pt-br'):
                with (
                    self.subTest(email=name, language=language),
                    translation.override(language),
                ):
                    email = getattr(emails, name)(
                        recipient_list=['owner@acme.com'], **KWARGS
                    )
                    message = email.get_message()
                    self.assertIn('Acme', message.subject)
                    html = message.alternatives[0][0]
                    self.assertIn('https://app.example.com/management/billing', html)
                    self.assertNotIn('<b>Inc</b>', html)

    def test_recipients_are_deduplicated(self):
        organization = OrganizationFactory()
        owner_email = organization.owner.user.email
        BillingProfileFactory(organization=organization, email=owner_email.upper())
        self.assertEqual(
            [email for email, _ in emails.recipients(organization)], [owner_email]
        )

    def test_billing_email_and_owner_both_receive(self):
        organization = OrganizationFactory()
        BillingProfileFactory(organization=organization, email='finance@acme.com')
        with self.captureOnCommitCallbacks(execute=True):
            emails.queue_billing_email(
                'PlanChangedEmail', organization, plan_name='Pro'
            )
        self.assertEqual(
            sorted(message.to[0] for message in mail.outbox),
            sorted([organization.owner.user.email, 'finance@acme.com']),
        )

    def test_unknown_email_module_is_refused(self):
        from apps.generics.tasks import send_email

        with (
            mock.patch('apps.billing.emails.PlanChangedEmail.send') as send,
            self.assertLogs('apps.generics.tasks', 'ERROR'),
        ):
            send_email.apply(
                kwargs={
                    'email_class_path': 'apps.other.Email',
                    'recipient_list': ['x@y.z'],
                    'kwargs': {},
                }
            )
        send.assert_not_called()
