from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import InvitationErrorMessages
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class InvitationDeclineTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory.create()
        self.user = UserFactory()
        self.decline_url_name = 'accounts:invitations-decline'

    def _decline_url(self, invitation):
        return reverse(
            self.decline_url_name,
            kwargs={'invitation_pk': invitation.pk},
        )

    def _create_invitation(self, **kwargs):
        defaults = {
            'organization': self.organization,
            'email': self.user.email,
        }
        defaults.update(kwargs)
        return InvitationFactory(**defaults)

    def test_decline_marks_declined(self):
        invitation = self._create_invitation()
        self.client.force_authenticate(user=self.user)
        url = self._decline_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'Invitation declined successfully.')
        invitation.refresh_from_db()
        self.assertTrue(invitation.is_declined)
        self.assertIsNotNone(invitation.declined_at)

    def test_decline_requires_authentication(self):
        invitation = self._create_invitation()
        url = self._decline_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_decline_requires_email_match(self):
        other_user = UserFactory()
        invitation = self._create_invitation()
        self.client.force_authenticate(user=other_user)
        url = self._decline_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_decline_fails_if_already_accepted(self):
        invitation = self._create_invitation(is_accepted=True)
        self.client.force_authenticate(user=self.user)
        url = self._decline_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            InvitationErrorMessages.INVITATION_ACCEPTED.label,
        )

    def test_decline_fails_if_already_declined(self):
        invitation = self._create_invitation(
            is_declined=True,
            declined_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.user)
        url = self._decline_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            InvitationErrorMessages.INVITATION_DECLINED.label,
        )

    def test_decline_fails_if_expired(self):
        invitation = self._create_invitation(
            is_expired=True,
            expired_at=timezone.now() - timedelta(days=1),
        )
        self.client.force_authenticate(user=self.user)
        url = self._decline_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            InvitationErrorMessages.INVITATION_EXPIRED.label,
        )
