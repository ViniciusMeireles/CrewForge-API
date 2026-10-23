from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.factories.users import DEFAULT_PASSWORD, UserFactory

BLOCKED_MESSAGE = 'Your account is blocked. Contact support.'


class BlockedSignInTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = UserFactory(blocked=True)
        self.url = reverse('accounts:token_obtain_pair')

    def sign_in(self, username, password):
        return self.client.post(
            self.url, data={'username': username, 'password': password}, format='json'
        )

    def test_correct_password_of_a_blocked_account(self):
        with self.assertLogs('security', level='WARNING') as logs:
            response = self.sign_in(self.user.username, DEFAULT_PASSWORD)

        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['error']['code'], 'ACCOUNT_BLOCKED')
        self.assertEqual(response.data['error']['message'], BLOCKED_MESSAGE)
        self.assertNotIn('access', response.data)
        self.assertTrue(any('account.blocked_sign_in' in line for line in logs.output))

    def test_wrong_password_keeps_the_generic_message(self):
        blocked = self.sign_in(self.user.username, 'wrong-password')
        unknown = self.sign_in('nobody-here', 'wrong-password')

        self.assertEqual(blocked.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(blocked.data['error']['code'], 'AUTHENTICATION_ERROR')
        self.assertEqual(blocked.data['error'], unknown.data['error'])

    def test_access_cookie_of_a_blocked_account_is_refused(self):
        access = RefreshToken.for_user(self.user).access_token
        client = APIClient()
        client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(access)

        response = client.get(reverse('accounts:session'))

        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['error']['code'], 'ACCOUNT_BLOCKED')

    def test_unblocked_account_signs_in(self):
        self.user.blocked_at = None
        self.user.save(update_fields=['blocked_at'])
        response = self.sign_in(self.user.username, DEFAULT_PASSWORD)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
