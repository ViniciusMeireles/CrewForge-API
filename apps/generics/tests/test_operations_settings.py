import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin

PROJECT = Path(settings.BASE_DIR)
PRODUCTION_ENV = {
    'DJANGO_SECRET_KEY': 'x' * 64,
    'NUM_PROXIES': '1',
    'MEDIA_ROOT': '/tmp/media',
    'ENVIRONMENT': 'production',
}


def run_python(code: str, **env) -> subprocess.CompletedProcess:
    clean = {
        key: value
        for key, value in os.environ.items()
        if key not in {'DJANGO_SETTINGS_MODULE', 'MEDIA_ROOT'}
    }
    return subprocess.run(
        [sys.executable, '-c', code],
        cwd=PROJECT,
        env={**clean, **env},
        capture_output=True,
        text=True,
        timeout=60,
    )


class EntrypointDefaultsTestCase(SimpleTestCase):
    def test_entrypoints_default_to_production(self):
        for module in ('config.wsgi', 'config.asgi', 'config.celery'):
            with self.subTest(module=module):
                result = run_python(
                    f'import {module}, os; print(os.environ["DJANGO_SETTINGS_MODULE"])',
                    **PRODUCTION_ENV,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    result.stdout.strip().splitlines()[-1], 'config.settings.production'
                )

    def test_production_requires_media_root(self):
        env = {k: v for k, v in PRODUCTION_ENV.items() if k != 'MEDIA_ROOT'}
        result = run_python('import config.settings.production', **env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('MEDIA_ROOT', result.stderr)

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
        result = run_python(
            'import config.settings.base as b; '
            'print(b.CACHES["default"]["BACKEND"]); '
            'print(b.DATABASES["default"]["CONN_MAX_AGE"]); '
            'print(b.DATABASES["default"]["CONN_HEALTH_CHECKS"]); '
            'print(b.TESTING)',
            DATABASE_URL='postgres://u:p@localhost:5432/db',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.split(),
            ['django.core.cache.backends.redis.RedisCache', '60', 'True', 'False'],
        )

    def test_empty_conn_max_age_uses_the_default(self):
        result = run_python(
            'import config.settings.base as b; '
            'print(b.DATABASES["default"]["CONN_MAX_AGE"])',
            DATABASE_URL='postgres://u:p@localhost:5432/db',
            CONN_MAX_AGE='',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split()[-1], '60')

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
