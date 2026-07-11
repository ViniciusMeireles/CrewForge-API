from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.users import DEFAULT_PASSWORD
from apps.accounts.tests.mixins import APITestCaseMixin

username_field = get_user_model().USERNAME_FIELD


class AuthPermissionTestCase(APITestCaseMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.token_url = reverse(viewname='accounts:token_obtain_pair')
        cls.logout_url = reverse(viewname='accounts:logout')
        cls.password_reset_url = reverse(viewname='accounts:password_reset')
        cls.password_reset_confirm_url = reverse(
            viewname='accounts:password_reset_confirm'
        )

    def setUp(self):
        self.organization = self.new_account()

    def test_not_authenticated_password_reset(self):
        self.client.logout()
        member = self.organization.owner
        payload = {'email': member.user.email}
        response = self.client.post(
            self.password_reset_url, data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('detail', response.data)

    def test_not_authenticated_logout(self):
        self.client.force_authenticate(user=None)
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        token_response = self.client.post(self.token_url, data=payload, format='json')
        refresh_token = token_response.data.get('refresh')
        response = self.client.post(
            self.logout_url, data={'refresh': refresh_token}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
