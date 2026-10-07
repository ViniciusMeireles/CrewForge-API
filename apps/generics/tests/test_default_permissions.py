from django.test import SimpleTestCase
from django.urls import NoReverseMatch, URLResolver, get_resolver, reverse
from rest_framework import status as http_status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.settings import api_settings
from rest_framework.test import APITestCase

PUBLIC_ROUTES = {
    'schema',
    'swagger-ui',
    'redoc',
    'accounts:token_obtain_pair',
    'accounts:token_refresh',
    'accounts:token_verify',
    'accounts:logout',
    'accounts:password_reset',
    'accounts:password_reset_confirm',
    'accounts:signup-list',
    'accounts:invitations-by-key',
    'accounts:session-config',
}


def iter_api_views(patterns=None, namespace=None, prefix=''):
    for pattern in patterns if patterns is not None else get_resolver().url_patterns:
        if isinstance(pattern, URLResolver):
            yield from iter_api_views(
                pattern.url_patterns,
                pattern.namespace or namespace,
                prefix + str(pattern.pattern),
            )
            continue
        view_class = getattr(pattern.callback, 'cls', None)
        route = prefix + str(pattern.pattern)
        if view_class is None or not route.startswith('api/'):
            continue
        name = f'{namespace}:{pattern.name}' if namespace else pattern.name
        initkwargs = getattr(pattern.callback, 'initkwargs', None) or {}
        permissions = initkwargs.get(
            'permission_classes', view_class.permission_classes
        )
        yield name, permissions


class DefaultPermissionTestCase(SimpleTestCase):
    def test_default_permission_is_authenticated(self):
        self.assertEqual(api_settings.DEFAULT_PERMISSION_CLASSES, [IsAuthenticated])

    def test_only_allowlisted_routes_are_public(self):
        public = {
            name
            for name, permissions in iter_api_views()
            if not permissions or AllowAny in permissions
        }
        self.assertEqual(public, PUBLIC_ROUTES)


class ApiRootPermissionTestCase(APITestCase):
    def test_api_roots_require_authentication(self):
        for url in ['/api/accounts/', '/api/teams/']:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(
                    response.status_code, http_status.HTTP_401_UNAUTHORIZED
                )

    def test_signup_has_no_detail_route(self):
        with self.assertRaises(NoReverseMatch):
            reverse('accounts:signup-detail', args=[1])
