import re

from django.conf import settings
from django.core import mail
from django.test import TestCase
from django.utils import translation

from apps.accounts.emails import (
    OrganizationReactivatedEmail,
    OrganizationSuspendedEmail,
    OwnershipTransferredNewOwnerEmail,
    OwnershipTransferredPreviousOwnerEmail,
)


def _rendered_text(message) -> str:
    parts = [message.body]
    parts += [content for content, _ in message.alternatives]
    return re.sub(r'\s+', ' ', ' '.join(parts))


class OrganizationNoticeEmailTestCase(TestCase):
    def send(self, email_class, **kwargs):
        email_class(
            recipient_list=['owner@example.com'],
            organization_name='Acme & Co',
            **kwargs,
        ).send()
        return mail.outbox[-1]

    def test_subjects_and_bodies(self):
        cases = [
            (
                OrganizationSuspendedEmail,
                {},
                'Your organization Acme & Co was suspended',
                f'was suspended by {settings.SYSTEM_TITLE}',
            ),
            (
                OrganizationReactivatedEmail,
                {},
                'Your organization Acme & Co is active again',
                'Its members can access it again.',
            ),
            (
                OwnershipTransferredNewOwnerEmail,
                {},
                'You are now the owner of Acme & Co',
                'to you.',
            ),
            (
                OwnershipTransferredPreviousOwnerEmail,
                {'new_owner_name': 'Maria <Silva>'},
                'Ownership of Acme & Co was transferred',
                'to Maria &lt;Silva&gt;. You remain a member as an admin.',
            ),
        ]
        for email_class, kwargs, subject, body in cases:
            with self.subTest(email=email_class.__name__):
                message = self.send(email_class, **kwargs)
                self.assertEqual(message.subject, subject)
                self.assertEqual(message.to, ['owner@example.com'])
                self.assertIn(body, _rendered_text(message))

    def test_names_are_escaped_in_the_html_body(self):
        message = self.send(OrganizationSuspendedEmail)
        html = message.alternatives[0][0]
        self.assertIn('Acme &amp; Co', html)
        self.assertNotIn('Acme & Co was suspended by', html)

    def test_rendered_in_portuguese(self):
        with translation.override('pt-br'):
            message = self.send(OrganizationReactivatedEmail)
        self.assertEqual(
            message.subject, 'Sua organização Acme & Co está ativa novamente'
        )
