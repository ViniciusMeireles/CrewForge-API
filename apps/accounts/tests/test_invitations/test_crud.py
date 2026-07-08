from datetime import timedelta

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import InvitationEmailErrorMessages, MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.models.invitation import Invitation
from apps.accounts.tests.mixins import APITestCaseMixin


class InvitationCRUDTestCase(APITestCaseMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.detail_url_name = 'accounts:invitations-detail'
        cls.list_url = reverse('accounts:invitations-list')
        cls.choices_url = reverse('accounts:invitations-choices')

    def setUp(self):
        self.organization = self.new_account()

    def _detail_url(self, invitation):
        return reverse(self.detail_url_name, args=[invitation.pk])

    def _create_invitation(self, **kwargs):
        return InvitationFactory(organization=self.organization, **kwargs)

    def test_list_invitations(self):
        self._create_invitation()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_list_only_active(self):
        InvitationFactory(organization=self.organization, is_active=False)
        response = self.client.get(self.list_url)
        for result in response.data['results']:
            self.assertTrue(result['is_active'])

    def test_choices_endpoint(self):
        self._create_invitation()
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_create_invitation(self):
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': invitation_data.role,
            'expired_at': invitation_data.expired_at,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], invitation_data.email)
        self.assertEqual(response.data['role'], invitation_data.role)
        self.assertEqual(
            response.data['expired_at'],
            invitation_data.expired_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        )
        self.assertEqual(response.data['organization'], self.organization.id)
        self.assertFalse(response.data['is_expired'])

    def test_retrieve_invitation(self):
        invitation = self._create_invitation()
        url = self._detail_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['email'], invitation.email)
        self.assertEqual(response.data['role'], invitation.role)
        self.assertEqual(
            response.data['expired_at'],
            invitation.expired_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        )
        self.assertFalse(response.data['is_expired'])
        self.assertEqual(response.data['organization'], self.organization.id)

    def test_update_invitation(self):
        invitation = self._create_invitation()
        url = self._detail_url(invitation)
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': MemberRoleChoices.ADMIN,
            'expired_at': invitation_data.expired_at,
            'organization': self.organization.id,
        }
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['email'], invitation_data.email)
        self.assertEqual(response.data['role'], MemberRoleChoices.ADMIN)
        self.assertEqual(
            response.data['expired_at'],
            invitation_data.expired_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        )

    def test_delete_invitation(self):
        invitation = self._create_invitation()
        url = self._detail_url(invitation)
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Invitation.objects.filter_actives().filter(id=invitation.id).exists()
        )

    def test_retrieve_expired_invitation(self):
        invitation = self._create_invitation(
            is_expired=True,
            expired_at=timezone.now() - timedelta(days=1),
        )
        url = self._detail_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data['is_expired'])
        self.assertEqual(
            response.data['expired_at'],
            invitation.expired_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        )

    def test_retrieve_accepted_invitation(self):
        invitation = self._create_invitation(is_accepted=True)
        url = self._detail_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data['is_accepted'])

    def test_create_duplicate_invitation_returns_400(self):
        invitation = self._create_invitation(
            expired_at=timezone.now() + timedelta(days=1),
            is_expired=False,
            is_accepted=False,
        )
        payload = {
            'email': invitation.email,
            'role': invitation.role,
            'expired_at': invitation.expired_at,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    @override_settings(FRONTEND_URL='http://example.com')
    def test_send_email_success(self):
        invitation = self._create_invitation(
            expired_at=timezone.now() + timedelta(days=7),
        )
        url = reverse('accounts:invitations-send-email', args=[invitation.pk])
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            response.data['detail'],
            InvitationEmailErrorMessages.SENT_SUCCESS.label,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(invitation.email, mail.outbox[0].to)
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.last_email_sent_at)

    @override_settings(FRONTEND_URL='http://example.com')
    def test_send_email_after_cooldown(self):
        invitation = self._create_invitation(
            expired_at=timezone.now() + timedelta(days=7),
            last_email_sent_at=timezone.now() - timedelta(seconds=61),
        )
        url = reverse('accounts:invitations-send-email', args=[invitation.pk])
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        invitation.refresh_from_db()
        five_secs_ago = timezone.now() - timedelta(seconds=5)
        self.assertGreater(invitation.last_email_sent_at, five_secs_ago)

    @override_settings(FRONTEND_URL='http://example.com')
    def test_create_invitation_with_send_email_true(self):
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': invitation_data.role,
            'expired_at': invitation_data.expired_at,
            'send_email': True,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(invitation_data.email, mail.outbox[0].to)
        invitation = Invitation.objects.get(id=response.data['id'])
        self.assertIsNotNone(invitation.last_email_sent_at)

    @override_settings(FRONTEND_URL='http://example.com')
    def test_create_invitation_with_send_email_false(self):
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': invitation_data.role,
            'expired_at': invitation_data.expired_at,
            'send_email': False,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 0)
        invitation = Invitation.objects.get(id=response.data['id'])
        self.assertIsNone(invitation.last_email_sent_at)

    @override_settings(FRONTEND_URL='http://example.com')
    def test_create_invitation_with_send_email_default(self):
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': invitation_data.role,
            'expired_at': invitation_data.expired_at,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 0)
        invitation = Invitation.objects.get(id=response.data['id'])
        self.assertIsNone(invitation.last_email_sent_at)
