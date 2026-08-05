from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class InvitationByKeyTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory.create()

    def _create_invitation(self, **kwargs):
        defaults = {'organization': self.organization}
        defaults.update(kwargs)
        return InvitationFactory(**defaults)

    def _by_key_url(self, invitation):
        return reverse(
            'accounts:invitations-by-key',
            kwargs={'invitation_key': invitation.key},
        )

    def test_by_key_returns_invitation_with_valid_key(self):
        invitation = self._create_invitation()
        url = self._by_key_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(str(response.data['key']), str(invitation.key))
        self.assertEqual(response.data['email'], invitation.email)

    def test_by_key_returns_404_for_invalid_key(self):
        from uuid import uuid4

        url = reverse(
            'accounts:invitations-by-key',
            kwargs={'invitation_key': uuid4()},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_by_key_returns_has_user_true_when_user_exists(self):
        user = UserFactory()
        invitation = self._create_invitation(email=user.email)
        url = self._by_key_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data['has_user'])

    def test_by_key_returns_has_user_false_when_no_user(self):
        invitation = self._create_invitation(email='nonexistent@example.com')
        url = self._by_key_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['has_user'])

    def test_by_key_is_public_no_auth_required(self):
        invitation = self._create_invitation()
        self.client.force_authenticate(user=None)
        url = self._by_key_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(str(response.data['key']), str(invitation.key))

    def test_by_key_authenticated_returns_own_invitation(self):
        user = UserFactory()
        invitation = self._create_invitation(email=user.email)
        self.client.force_authenticate(user=user)
        url = self._by_key_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['email'], user.email)
        self.assertTrue(response.data['has_user'])

    def test_by_key_authenticated_returns_404_for_other_invitation(self):
        invitation = self._create_invitation(email='other@example.com')
        user = UserFactory()
        self.client.force_authenticate(user=user)
        url = self._by_key_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
