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
        self.assertEqual(response.data['preferred_language'], 'en')

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

    def test_update_preferred_language(self):
        response = self.client.patch(
            self.profile_url,
            data={'preferred_language': 'pt-br'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['preferred_language'], 'pt-br')
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_language, 'pt-br')

    def test_update_preferred_language_invalid_value(self):
        response = self.client.patch(
            self.profile_url,
            data={'preferred_language': 'fr'},
            format='json',
            HTTP_ACCEPT_LANGUAGE='pt-BR',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        error = response.data['error']
        self.assertEqual(error['code'], 'VALIDATION_ERROR')
        self.assertEqual(error['message'], 'Um ou mais campos são inválidos.')
        detail = error['details']['preferred_language'][0]
        self.assertIsInstance(detail, str)
        self.assertTrue(detail)
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_language, 'en')

    def test_update_preferred_language_rejects_uppercase_locale(self):
        response = self.client.patch(
            self.profile_url,
            data={'preferred_language': 'pt-BR'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_language, 'en')

    def test_update_preferred_language_rejects_null(self):
        response = self.client.patch(
            self.profile_url,
            data={'preferred_language': None},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_language, 'en')

    def test_partial_update_without_preferred_language_keeps_value(self):
        self.user.preferred_language = 'pt-br'
        self.user.save(update_fields=['preferred_language'])
        response = self.client.patch(
            self.profile_url,
            data={'last_name': 'KeptLastName'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_language, 'pt-br')

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
