from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.users import UserFactory


class UserProfilePermissionTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.profile_url = reverse('accounts:users-me')
        cls.change_password_url = reverse('accounts:users-me-change-password')

    def test_not_authenticated_retrieve(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_update(self):
        response = self.client.patch(
            self.profile_url,
            data={'first_name': 'Hacker'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_change_password(self):
        response = self.client.post(
            self.change_password_url,
            data={
                'current_password': 'passWord*123',
                'new_password': 'newPass*456',
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_access(self):
        user = UserFactory.create()
        self.client.force_authenticate(user=user)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
