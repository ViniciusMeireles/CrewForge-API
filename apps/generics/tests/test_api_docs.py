from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.users import UserFactory
from apps.generics.permissions import ApiDocsPermission
from apps.generics.tests.test_default_permissions import iter_api_views
from config.settings import base
from config.settings.checks import normalize_admin_url

DOCS_ROUTES = ['schema', 'swagger-ui', 'redoc']


class ApiDocsAccessTestCase(APITestCase):
    def assert_docs_status(self, expected: int):
        for name in DOCS_ROUTES:
            with self.subTest(route=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, expected)

    def test_docs_routes_use_docs_permission(self):
        permissions = dict(iter_api_views())
        for name in DOCS_ROUTES:
            with self.subTest(route=name):
                self.assertEqual(permissions[name], [ApiDocsPermission])

    @override_settings(DEBUG=True, API_DOCS_PUBLIC=None)
    def test_public_in_debug_by_default(self):
        self.assert_docs_status(http_status.HTTP_200_OK)

    @override_settings(DEBUG=False, API_DOCS_PUBLIC=True)
    def test_public_when_enabled(self):
        self.assert_docs_status(http_status.HTTP_200_OK)

    @override_settings(DEBUG=False, API_DOCS_PUBLIC=None)
    def test_anonymous_denied_without_debug(self):
        self.assert_docs_status(http_status.HTTP_401_UNAUTHORIZED)

    @override_settings(DEBUG=True, API_DOCS_PUBLIC=False)
    def test_disabled_overrides_debug(self):
        self.assert_docs_status(http_status.HTTP_401_UNAUTHORIZED)

    @override_settings(DEBUG=False, API_DOCS_PUBLIC=False)
    def test_non_staff_user_denied(self):
        self.client.force_login(UserFactory())
        self.assert_docs_status(http_status.HTTP_403_FORBIDDEN)

    @override_settings(DEBUG=False, API_DOCS_PUBLIC=False)
    def test_staff_session_allowed(self):
        self.client.force_login(UserFactory(is_staff=True))
        self.assert_docs_status(http_status.HTTP_200_OK)

    def test_root_redirect_is_temporary(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, http_status.HTTP_302_FOUND)


class SecuritySettingsTestCase(SimpleTestCase):
    def test_hsts_defaults_to_one_year_without_preload(self):
        self.assertEqual(base.SECURE_HSTS_SECONDS, 31536000)
        self.assertTrue(base.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertFalse(base.SECURE_HSTS_PRELOAD)

    def test_admin_is_served_at_admin_url(self):
        self.assertEqual(reverse('admin:index'), f'/{base.ADMIN_URL}')

    def test_admin_url_is_normalized(self):
        self.assertEqual(normalize_admin_url('/backoffice'), 'backoffice/')
        self.assertEqual(normalize_admin_url('ops/admin/'), 'ops/admin/')

    def test_admin_url_must_not_be_empty(self):
        for value in ['', '/', '  ']:
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                normalize_admin_url(value)
