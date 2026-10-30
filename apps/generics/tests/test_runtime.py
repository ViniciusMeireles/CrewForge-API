import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.db import OperationalError
from django.test import SimpleTestCase, override_settings
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework import status as http_status
from rest_framework.test import APITestCase

PROJECT = Path(settings.BASE_DIR)


class HealthEndpointsTestCase(APITestCase):
    def test_healthz_is_public_and_minimal(self):
        response = self.client.get('/healthz')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_readyz_checks_database_and_cache(self):
        response = self.client.get('/readyz')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_readyz_unavailable_when_database_is_down(self):
        with mock.patch(
            'apps.generics.middleware.connection.cursor',
            side_effect=OperationalError('down'),
        ):
            response = self.client.get('/readyz')
        self.assertEqual(response.status_code, http_status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.json(), {'status': 'unavailable'})

    def test_readyz_unavailable_when_cache_is_down(self):
        with mock.patch(
            'apps.generics.middleware.cache.set',
            side_effect=RedisConnectionError('down'),
        ):
            response = self.client.get('/readyz')
        self.assertEqual(response.status_code, http_status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_readyz_unavailable_when_cache_loses_writes(self):
        with mock.patch('apps.generics.middleware.cache.get', return_value=None):
            response = self.client.get('/readyz')
        self.assertEqual(response.status_code, http_status.HTTP_503_SERVICE_UNAVAILABLE)

    @override_settings(ALLOWED_HOSTS=['api.example.com'], SECURE_SSL_REDIRECT=True)
    def test_probes_answer_any_host_without_redirect(self):
        response = self.client.get('/healthz', HTTP_HOST='127.0.0.1:8000')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_health_is_never_throttled(self):
        with mock.patch(
            'rest_framework.throttling.SimpleRateThrottle.allow_request',
            return_value=False,
        ):
            self.assertEqual(self.client.get('/healthz').status_code, 200)


class StartupScriptsTestCase(SimpleTestCase):
    def test_api_start_does_not_migrate(self):
        run = (PROJECT / 'run.sh').read_text()
        production = run.split('if [ "$ENVIRONMENT" = "production" ]; then', 1)[1]
        production = production.split('elif', 1)[0]
        self.assertNotIn('migrate', production)
        self.assertNotIn('collectstatic', production)
        self.assertIn('gunicorn', production)

    def test_migrate_script_only_migrates(self):
        script = (PROJECT / 'migrate.sh').read_text()
        self.assertIn('migrate --noinput', script)
        self.assertNotIn('collectstatic', script)
        self.assertNotIn('compilemessages', script)

    def test_image_static_root_is_writable_by_the_app_user(self):
        dockerfile = (PROJECT / 'Dockerfile').read_text()
        self.assertRegex(
            dockerfile, r'chown -R \$\{USER_NAME\}:\$\{USER_NAME\} [^\n]*/staticfiles'
        )

    def test_image_ships_static_files_and_catalogs(self):
        dockerfile = (PROJECT / 'Dockerfile').read_text()
        self.assertIn('ENV STATIC_ROOT=/staticfiles', dockerfile)
        self.assertIn('python manage.py collectstatic --noinput', dockerfile)
        self.assertIn('msgfmt', dockerfile)

    def test_image_is_pinned_and_least_privilege(self):
        dockerfile = (PROJECT / 'Dockerfile').read_text()
        self.assertRegex(dockerfile, r'FROM python:3\.14\.\d+-slim')
        self.assertRegex(dockerfile, r'ghcr\.io/astral-sh/uv:\d+\.\d+\.\d+')
        self.assertNotRegex(dockerfile, re.compile(r'chown[^\n]*/bin'))
        self.assertIn('HEALTHCHECK', dockerfile)
        self.assertIn('USER ${USER_NAME}', dockerfile)
