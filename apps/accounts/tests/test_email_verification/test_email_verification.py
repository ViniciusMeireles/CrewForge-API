import importlib
import re

from django.apps import apps as django_apps
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.accounts.utils.email_verification import verification_url

VERIFY_URL = 'http://app.test/auth/verify-email'


def link_params(url: str) -> dict:
    return dict(re.findall(r'(uid|token)=([^&\s"]+)', url))


@override_settings(FRONTEND_VERIFY_EMAIL_URL=VERIFY_URL)
class EmailVerificationTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.verify_url = reverse('accounts:email_verify')
        self.resend_url = reverse('accounts:email_verify_resend')

    def unverified_user(self, **kwargs):
        return UserFactory(email_verified_at=None, **kwargs)

    def test_signup_sends_verification_email_and_starts_unverified(self):
        user = UserFactory.build()
        organization = OrganizationFactory.build()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('accounts:signup-list'),
                {
                    'user': {
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'password': 'Passw0rd*123',
                    },
                    'organization': {
                        'name': organization.name,
                        'slug': organization.slug,
                    },
                    'nickname': MemberFactory.build().nickname,
                },
                format='json',
            )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertFalse(get_user(response.data['user']['id']).email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])
        self.assertIn(
            VERIFY_URL, mail.outbox[0].body + str(mail.outbox[0].alternatives)
        )

    def test_confirm_verifies_and_link_cannot_be_reused(self):
        user = self.unverified_user()
        params = link_params(verification_url(user))

        response = self.client.post(self.verify_url, params, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

        again = self.client.post(self.verify_url, params, format='json')
        self.assertEqual(again.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_confirm_rejects_invalid_links(self):
        user = self.unverified_user()
        params = link_params(verification_url(user))
        cases = {
            'bad token': {**params, 'token': 'invalid-token'},
            'bad uid': {**params, 'uid': 'invalid'},
            'missing': {},
        }
        for name, payload in cases.items():
            with self.subTest(name=name):
                response = self.client.post(self.verify_url, payload, format='json')
                self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_link_for_old_email_is_invalid_after_email_change(self):
        user = self.unverified_user()
        params = link_params(verification_url(user))
        user.email = 'changed@example.test'
        user.save(update_fields=['email'])

        response = self.client.post(self.verify_url, params, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_resend_sends_only_when_unverified(self):
        user = self.unverified_user()
        self.client.force_authenticate(user=user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.resend_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        self.client.force_authenticate(user=UserFactory())
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.resend_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_requires_authentication(self):
        response = self.client.post(self.resend_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_profile_email_change_requires_new_verification(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                reverse('accounts:users-me'),
                {'email': 'new-address@example.test'},
                format='json',
            )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['email_verified'])
        self.assertEqual(mail.outbox[-1].to, ['new-address@example.test'])

    def test_profile_update_keeps_verification_when_email_is_unchanged(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                reverse('accounts:users-me'),
                {'email': user.email, 'first_name': 'Same'},
                format='json',
            )
        self.assertTrue(response.data['email_verified'])
        self.assertEqual(len(mail.outbox), 0)

    def test_create_with_invite_marks_email_verified(self):
        organization = OrganizationFactory()
        user = UserFactory.build()
        invitation = InvitationFactory(
            organization=organization, email=user.email, expired_at=None
        )
        response = self.client.post(
            reverse('accounts:members-create-with-invite', args=[invitation.key]),
            {
                'user': {
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'password': 'Passw0rd*123',
                },
                'nickname': MemberFactory.build().nickname,
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        created = get_user(response.data['user']['id'])
        self.assertTrue(created.email_verified)


def get_user(pk):
    return django_apps.get_model('accounts', 'User').objects.get(pk=pk)


class UnverifiedInvitationsTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.user = UserFactory(email_verified_at=None)
        self.invitation = InvitationFactory(
            organization=OrganizationFactory(), email=self.user.email
        )
        self.client.force_authenticate(user=self.user)

    def test_unverified_user_does_not_see_email_invitations(self):
        response = self.client.get(reverse('accounts:invitations-received'))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_unverified_user_cannot_accept_or_decline(self):
        for name in ['accounts:invitations-accept', 'accounts:invitations-decline']:
            with self.subTest(name=name):
                url = reverse(name, kwargs={'invitation_pk': self.invitation.pk})
                response = self.client.post(url, format='json')
                self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_verified_user_sees_and_accepts(self):
        self.user.email_verified_at = self.user.date_joined
        self.user.save(update_fields=['email_verified_at'])
        response = self.client.get(reverse('accounts:invitations-received'))
        self.assertEqual(response.data['count'], 1)
        accept = self.client.post(
            reverse(
                'accounts:invitations-accept',
                kwargs={'invitation_pk': self.invitation.pk},
            ),
            format='json',
        )
        self.assertEqual(accept.status_code, http_status.HTTP_200_OK)

    def test_unverified_user_can_open_invitation_by_key(self):
        response = self.client.get(
            reverse('accounts:invitations-by-key', args=[self.invitation.key])
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_session_exposes_email_verified(self):
        member = MemberFactory(user=self.user)
        self.client.force_authenticate(member=member)
        response = self.client.get(reverse('accounts:session'))
        self.assertFalse(response.data['user']['email_verified'])


class MarkExistingUsersVerifiedMigrationTestCase(TestCase):
    def test_marks_users_without_verification_date(self):
        migration = importlib.import_module(
            'apps.accounts.migrations.0004_user_email_verified_at'
        )
        user = UserFactory(email_verified_at=None)
        migration.mark_existing_users_verified(django_apps, None)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
