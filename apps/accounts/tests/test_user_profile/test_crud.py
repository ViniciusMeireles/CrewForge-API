from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.users import UserFactory

User = get_user_model()


class UserProfileCRUDTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.profile_url = reverse('accounts:users-me')
        cls.change_password_url = reverse('accounts:users-me-change-password')

    def setUp(self):
        self.user = UserFactory.create()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_profile(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.user.id)
        self.assertEqual(response.data['username'], self.user.username)
        self.assertEqual(response.data['email'], self.user.email)

    def test_update_profile(self):
        response = self.client.patch(
            self.profile_url,
            data={'first_name': 'UpdatedName', 'email': 'new@example.com'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'UpdatedName')
        self.assertEqual(response.data['email'], 'new@example.com')

    def test_update_username_blocked(self):
        response = self.client.patch(
            self.profile_url,
            data={'username': 'hacker-username'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.username, 'hacker-username')

    def test_update_partial_fields(self):
        response = self.client.patch(
            self.profile_url,
            data={'last_name': 'NewLastName'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['last_name'], 'NewLastName')

    def test_change_password(self):
        response = self.client.post(
            self.change_password_url,
            data={
                'current_password': 'passWord*123',
                'new_password': 'newPass*456',
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('detail', response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newPass*456'))

    def test_change_password_wrong_current(self):
        response = self.client.post(
            self.change_password_url,
            data={
                'current_password': 'wrong-password',
                'new_password': 'newPass*456',
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('current_password', response.data['error']['details'])

    def test_change_password_same_password(self):
        response = self.client.post(
            self.change_password_url,
            data={
                'current_password': 'passWord*123',
                'new_password': 'passWord*123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_change_password_too_short(self):
        response = self.client.post(
            self.change_password_url,
            data={
                'current_password': 'passWord*123',
                'new_password': 'short',
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data['error']['details'])

    def test_change_password_wrong_method(self):
        response = self.client.get(self.change_password_url)
        self.assertEqual(response.status_code, http_status.HTTP_405_METHOD_NOT_ALLOWED)
