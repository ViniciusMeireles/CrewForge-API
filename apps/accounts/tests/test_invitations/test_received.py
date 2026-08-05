from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class InvitationReceivedTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory.create()
        self.user = UserFactory()
        self.received_url = reverse('accounts:invitations-received')

    def _detail_url(self, invitation):
        return reverse(
            'accounts:invitations-received-detail',
            kwargs={'invitation_pk': invitation.pk},
        )

    def _create_invitation(self, **kwargs):
        defaults = {'organization': self.organization}
        defaults.update(kwargs)
        return InvitationFactory(**defaults)

    def test_received_lists_invitations_for_authenticated_user(self):
        self._create_invitation(email=self.user.email)
        self._create_invitation(email='other@example.com')
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.received_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['email'], self.user.email)

    def test_received_filters_by_email(self):
        self._create_invitation(email=self.user.email)
        self._create_invitation(email=self.user.email)
        self._create_invitation(email='other@example.com')
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.received_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        for result in response.data['results']:
            self.assertEqual(result['email'], self.user.email)

    def test_received_requires_authentication(self):
        self._create_invitation(email=self.user.email)
        response = self.client.get(self.received_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_received_pagination(self):
        emails = [f'user{i}@example.com' for i in range(5)]
        for email in emails:
            self._create_invitation(email=email)
        user = UserFactory(email=emails[0])
        self.client.force_authenticate(user=user)
        response = self.client.get(self.received_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)

    def test_received_includes_organization_name(self):
        self._create_invitation(email=self.user.email)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.received_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        result = response.data['results'][0]
        self.assertIn('organization_name', result)
        self.assertEqual(result['organization_name'], self.organization.name)

    def test_received_detail_returns_invitation(self):
        invitation = self._create_invitation(email=self.user.email)
        self.client.force_authenticate(user=self.user)
        url = self._detail_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['id'], invitation.id)
        self.assertEqual(response.data['email'], self.user.email)

    def test_received_detail_requires_authentication(self):
        invitation = self._create_invitation(email=self.user.email)
        url = self._detail_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_received_detail_404_for_other_user(self):
        invitation = self._create_invitation(email='other@example.com')
        self.client.force_authenticate(user=self.user)
        url = self._detail_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_received_detail_includes_organization(self):
        invitation = self._create_invitation(email=self.user.email)
        self.client.force_authenticate(user=self.user)
        url = self._detail_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        org = response.data['organization']
        self.assertIn('id', org)
        self.assertIn('name', org)
        self.assertIn('description', org)
        self.assertIn('logo_url', org)
