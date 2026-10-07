from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.settings.checks import (
    DEVELOPMENT_ENVIRONMENTS,
    MIN_SECRET_LENGTH,
    require_secret,
)


class RequireSecretTestCase(SimpleTestCase):
    def test_rejects_missing_short_or_development_keys(self):
        for value in [
            None,
            '',
            'x' * (MIN_SECRET_LENGTH - 1),
            'django-insecure-' + 'x' * 60,
        ]:
            with self.subTest(value=value):
                with self.assertRaises(ImproperlyConfigured):
                    require_secret('DJANGO_SECRET_KEY', value)

    def test_accepts_long_random_key(self):
        value = 'k' * MIN_SECRET_LENGTH
        self.assertEqual(require_secret('DJANGO_SECRET_KEY', value), value)


class DevelopmentEnvironmentsTestCase(SimpleTestCase):
    def test_production_is_not_a_development_environment(self):
        self.assertNotIn('production', DEVELOPMENT_ENVIRONMENTS)
        self.assertNotIn(None, DEVELOPMENT_ENVIRONMENTS)
