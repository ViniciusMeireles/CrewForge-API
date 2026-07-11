from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin


class SessionPermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.session_url = reverse('accounts:session')

    def test_not_authenticated_returns_401(self):
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_active_member_returns_200_but_no_org_context(self):
        organization = self.new_account(organization_login=True)
        organization.owner.is_active = False
        organization.owner.save()
        self.client.force_authenticate(user=organization.owner.user)
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsNotNone(response.data['user'])
        self.assertIsNotNone(response.data['organizations'])
        self.assertIsNone(response.data['organization'])
        self.assertIsNone(response.data['member'])
