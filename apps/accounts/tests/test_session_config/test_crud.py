from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin


class SessionConfigCRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.config_url = reverse('accounts:session-config')

    def test_unauthenticated_returns_200(self):
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_response_contains_expected_keys(self):
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('cookie_settings', response.data)
        self.assertIn('cors_allowed_origins', response.data)
        self.assertIn('cors_allow_credentials', response.data)
        self.assertIn('session_configured', response.data)
        self.assertIn('debug', response.data)

    def test_cookie_settings_contains_expected_keys(self):
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        cookie_settings = response.data['cookie_settings']
        self.assertIn('session_cookie_samesite', cookie_settings)
        self.assertIn('session_cookie_secure', cookie_settings)
        self.assertIn('csrf_cookie_samesite', cookie_settings)
        self.assertIn('csrf_cookie_secure', cookie_settings)

    def test_session_configured_false_when_unauthenticated(self):
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['session_configured'])

    def test_session_configured_true_when_authenticated_with_org(self):
        self.new_account(organization_login=True)
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data['session_configured'])

    def test_session_configured_false_when_authenticated_without_org(self):
        self.new_account(organization_login=False)
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['session_configured'])

    def test_cors_allow_credentials_is_boolean(self):
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsInstance(response.data['cors_allow_credentials'], bool)

    def test_debug_is_boolean(self):
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsInstance(response.data['debug'], bool)

    def test_cors_allowed_origins_is_list(self):
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsInstance(response.data['cors_allowed_origins'], list)
