import os
import runpy
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin

PROJECT = Path(settings.BASE_DIR)
PRODUCTION_ENV = {
    'DJANGO_SECRET_KEY': 'x' * 64,
    'NUM_PROXIES': '1',
    'MEDIA_ROOT': '/srv/media',
    'ENVIRONMENT': 'production',
    'DATABASE_URL': 'postgres://u:p@localhost:5432/db',
}


@contextmanager
def fresh_settings(unset=(), **env):
    with mock.patch.dict(os.environ, env), mock.patch.dict(sys.modules):
        for key in ('DJANGO_SETTINGS_MODULE', 'CONN_MAX_AGE', *unset):
            if key not in env:
                os.environ.pop(key, None)
        for name in [m for m in sys.modules if m.startswith('config.settings.')]:
            del sys.modules[name]
        yield


class EntrypointDefaultsTestCase(SimpleTestCase):
    def test_entrypoints_default_to_production(self):
        for name in ('wsgi', 'asgi', 'celery'):
            with self.subTest(module=name), mock.patch.dict(os.environ):
                os.environ.pop('DJANGO_SETTINGS_MODULE', None)
                runpy.run_path(str(PROJECT / 'config' / f'{name}.py'))
                self.assertEqual(
                    os.environ['DJANGO_SETTINGS_MODULE'], 'config.settings.production'
                )

    def test_production_requires_media_root(self):
        env = {k: v for k, v in PRODUCTION_ENV.items() if k != 'MEDIA_ROOT'}
        with (
            fresh_settings(unset=('MEDIA_ROOT',), **env),
            self.assertRaisesMessage(ImproperlyConfigured, 'MEDIA_ROOT'),
        ):
            import config.settings.production  # noqa: F401

    def test_production_loads_with_required_env(self):
        with fresh_settings(**PRODUCTION_ENV):
            import config.settings.production as production
        self.assertFalse(production.DEBUG)
        self.assertEqual(production.MEDIA_ROOT, '/srv/media')

    def test_only_local_settings_read_dotenv(self):
        sources = {
            name: (PROJECT / 'config' / 'settings' / f'{name}.py').read_text()
            for name in ('base', 'production', 'local')
        }
        self.assertNotIn('dotenv', sources['base'])
        self.assertNotIn('dotenv', sources['production'])
        self.assertIn('from . import dotenv', sources['local'])


class SharedInfrastructureSettingsTestCase(SimpleTestCase):
    def test_base_uses_redis_cache_and_connection_reuse(self):
        with fresh_settings(DATABASE_URL=PRODUCTION_ENV['DATABASE_URL']):
            import config.settings.base as base
        self.assertEqual(
            base.CACHES['default']['BACKEND'],
            'django.core.cache.backends.redis.RedisCache',
        )
        self.assertEqual(base.DATABASES['default']['CONN_MAX_AGE'], 60)
        self.assertTrue(base.DATABASES['default']['CONN_HEALTH_CHECKS'])
        self.assertFalse(base.TESTING)

    def test_empty_conn_max_age_uses_the_default(self):
        with fresh_settings(
            DATABASE_URL=PRODUCTION_ENV['DATABASE_URL'], CONN_MAX_AGE=''
        ):
            import config.settings.base as base
        self.assertEqual(base.DATABASES['default']['CONN_MAX_AGE'], 60)

    def test_celery_keeps_the_json_root_logger(self):
        self.assertFalse(settings.CELERY_WORKER_HIJACK_ROOT_LOGGER)

    def test_testing_settings_flag_tests(self):
        self.assertTrue(settings.TESTING)


class ServedSchemaTestCase(APITestCaseMixin, APITestCase):
    def test_served_schema_includes_audit_and_platform(self):
        self.client.force_authenticate(user=UserFactory(is_staff=True))
        response = self.client.get(reverse('schema'), {'format': 'json'})
        self.assertEqual(response.status_code, 200, response.content[:200])
        paths = response.json()['paths']
        self.assertTrue(any(p.startswith('/api/audit/') for p in paths))
        self.assertTrue(any(p.startswith('/api/platform/') for p in paths))
