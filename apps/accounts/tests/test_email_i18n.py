import re

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import translation
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import DEFAULT_PASSWORD, UserFactory
from apps.accounts.tasks import send_password_reset_email
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.accounts.utils.email_verification import send_verification_email

VERIFY_URL = 'http://app.test/auth/verify-email'
RESET_URL = 'http://app.test/auth/reset-password?uid=u&token=t'


def _rendered_text(message) -> str:
    parts = [message.body]
    parts += [content for content, _ in message.alternatives]
    return re.sub(r'\s+', ' ', ' '.join(parts))


@override_settings(FRONTEND_VERIFY_EMAIL_URL=VERIFY_URL)
class EmailLanguageTestCase(APITestCaseMixin, APITestCase):
    def _signup_payload(self) -> dict:
        user = UserFactory.build()
        organization = OrganizationFactory.build()
        return (
            user,
            organization,
            {
                'user': {
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'password': DEFAULT_PASSWORD,
                },
                'organization': {
                    'name': organization.name,
                    'slug': organization.slug,
                },
                'nickname': MemberFactory.build().nickname,
            },
        )

    def test_signup_verification_email_uses_initialized_preference(self):
        _, _, payload = self._signup_payload()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('accounts:signup-list'),
                payload,
                format='json',
                HTTP_ACCEPT_LANGUAGE='pt-BR',
            )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        text = _rendered_text(message)
        self.assertIn('Verifique seu endereço de e-mail', text)
        self.assertIn('Verificar e-mail', text)
        self.assertEqual(message.subject, 'Verifique seu e-mail')

    def test_signup_verification_email_defaults_to_english(self):
        _, _, payload = self._signup_payload()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('accounts:signup-list'), payload, format='json'
            )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        text = _rendered_text(message)
        self.assertIn('Verify your email address', text)
        self.assertIn('Verify Email', text)
        self.assertEqual(message.subject, 'Verify your email')

    def test_password_reset_email_renders_in_portuguese(self):
        with translation.override('pt-br'):
            send_password_reset_email(RESET_URL, ['user@example.com'])
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        text = _rendered_text(message)
        self.assertIn('Solicitação de recuperação de senha', text)
        self.assertIn('Redefinir senha', text)
        self.assertEqual(message.subject, 'Recuperação de senha')

    def test_task_applies_explicit_language_outside_override(self):
        send_password_reset_email(RESET_URL, ['user@example.com'], language='pt-br')
        self.assertEqual(len(mail.outbox), 1)
        text = _rendered_text(mail.outbox[0])
        self.assertIn('Solicitação de recuperação de senha', text)
        self.assertIn('Redefinir senha', text)

    def test_task_defaults_to_current_language(self):
        with translation.override('en'):
            send_password_reset_email(RESET_URL, ['user@example.com'])
        self.assertEqual(len(mail.outbox), 1)
        text = _rendered_text(mail.outbox[0])
        self.assertIn('Password Reset Request', text)
        self.assertIn('Reset Password', text)

    def test_resolved_language_is_captured_before_on_commit(self):
        user = UserFactory(email_verified_at=None, preferred_language='pt-br')
        with translation.override('pt-br'):
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                self.assertTrue(send_verification_email(user))
        with translation.override('en'):
            for callback in callbacks:
                callback()
        self.assertEqual(len(mail.outbox), 1)
        text = _rendered_text(mail.outbox[0])
        self.assertIn('Verifique seu endereço de e-mail', text)
        self.assertIn('Verificar e-mail', text)

    @override_settings(FRONTEND_URL='http://example.com')
    def test_invitation_email_uses_inviter_request_language(self):
        organization = self.new_account()
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': invitation_data.role,
            'expired_at': invitation_data.expired_at,
            'send_email': True,
        }
        response = self.client.post(
            reverse('accounts:invitations-list'),
            data=payload,
            format='json',
            HTTP_ACCEPT_LANGUAGE='pt-BR',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(
            message.subject,
            f'Você foi convidado a participar de {organization.name}',
        )
        text = _rendered_text(message)
        self.assertIn('Aceitar convite', text)

    @override_settings(FRONTEND_URL='http://example.com')
    def test_invitation_email_uses_invitee_preferred_language(self):
        organization = self.new_account()
        UserFactory.create(email='jane@example.com', preferred_language='pt-br')
        invitation_data = InvitationFactory.build()
        payload = {
            'email': 'Jane@example.com',
            'role': invitation_data.role,
            'expired_at': invitation_data.expired_at,
            'send_email': True,
        }
        response = self.client.post(
            reverse('accounts:invitations-list'),
            data=payload,
            format='json',
            HTTP_ACCEPT_LANGUAGE='en',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            f'Você foi convidado a participar de {organization.name}',
        )

    @override_settings(FRONTEND_URL='http://example.com')
    def test_invitation_email_without_request_defaults_to_english(self):
        organization = self.new_account()
        invitation = InvitationFactory.create(
            organization=organization,
            email='nobody@example.com',
            expired_at=None,
        )
        invitation.send_email()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            f'You have been invited to join {organization.name}',
        )

    @override_settings(FRONTEND_URL='http://example.com')
    def test_invitation_resend_uses_invitee_preferred_language(self):
        organization = self.new_account()
        invitation = InvitationFactory.create(
            organization=organization,
            email='Jane@example.com',
            expired_at=None,
        )
        UserFactory.create(email='jane@example.com', preferred_language='pt-br')
        response = self.client.post(
            reverse('accounts:invitations-send-email', args=[invitation.pk]),
            format='json',
            HTTP_ACCEPT_LANGUAGE='en',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            f'Você foi convidado a participar de {organization.name}',
        )

    def test_password_reset_email_uses_recipient_preferred_language(self):
        user = UserFactory.create(preferred_language='pt-br')
        response = self.client.post(
            reverse('accounts:password_reset'),
            data={'email': user.email},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Recuperação de senha')

    def test_verification_email_uses_recipient_preferred_language(self):
        user = UserFactory.create(email_verified_at=None, preferred_language='en')
        self.client.force_authenticate(user=user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('accounts:email_verify_resend'),
                HTTP_ACCEPT_LANGUAGE='pt-BR',
            )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Verify your email')
