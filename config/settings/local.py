import os

from .base import *  # noqa
from .base import (
    BASE_DIR,
    INSTALLED_APPS,
)

DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = ['*']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = os.environ.get('MEDIA_URL', '/media/')
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_SSL_REDIRECT = False

DEV_THIRD_PARTY_APPS = [
    'django_extensions',
]

INSTALLED_APPS += DEV_THIRD_PARTY_APPS

CORS_ALLOW_ALL_ORIGINS = True

CELERY_TASK_ALWAYS_EAGER = (
    os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'False').lower() == 'true'
)
