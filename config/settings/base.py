import os
import sys
import warnings
from datetime import timedelta
from pathlib import Path

import dj_database_url
from corsheaders.defaults import default_headers as default_cors_headers
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy
from dotenv import load_dotenv

from .checks import normalize_admin_url

load_dotenv()


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
TESTING = 'test' in sys.argv
ENVIRONMENT = os.getenv('ENVIRONMENT', None)

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')


# Application definition

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'django_filters',
    'drf_spectacular',
    'drf_spectacular_sidecar',
    'nested_admin',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'whitenoise.runserver_nostatic',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.teams',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE_DJANGO = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

MIDDLEWARE_THIRD_PARTY = [
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

MIDDLEWARE_LOCAL = []

MIDDLEWARE = MIDDLEWARE_THIRD_PARTY + MIDDLEWARE_DJANGO + MIDDLEWARE_LOCAL

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

WSGI_APPLICATION = 'config.wsgi.application'

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', 31536000))
SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    os.environ.get('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'True').lower() == 'true'
)
SECURE_HSTS_PRELOAD = os.environ.get('SECURE_HSTS_PRELOAD', 'False').lower() == 'true'
SECURE_SSL_REDIRECT = True

if os.environ.get('SECURE_PROXY_SSL_HEADER', 'False').lower() == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {'default': dj_database_url.config(default=os.environ.get('DATABASE_URL'))}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.'
        'UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'
LANGUAGES = [
    ('en', gettext_lazy('English')),
    ('pt-br', gettext_lazy('Portuguese')),
]

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_ROOT = os.environ.get('STATIC_ROOT', os.path.join(BASE_DIR, 'staticfiles'))
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = os.environ.get('MEDIA_URL', '/media/')
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', '/media/')

STORED_FILE_MAX_SIZE = int(os.environ.get('STORED_FILE_MAX_SIZE', 10 * 1024 * 1024))
STORED_FILE_IMAGE_CONTENT_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
STORED_FILE_ALLOWED_CONTENT_TYPES = [
    *STORED_FILE_IMAGE_CONTENT_TYPES,
    'application/pdf',
    'text/plain',
    'text/csv',
    'application/json',
    'application/zip',
    'application/msword',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.oasis.opendocument.text',
    'application/vnd.oasis.opendocument.spreadsheet',
    'application/vnd.oasis.opendocument.presentation',
]
STORED_FILE_INLINE_CONTENT_TYPES = STORED_FILE_IMAGE_CONTENT_TYPES
FILE_UPLOAD_HANDLERS = [
    'apps.accounts.utils.files.MaxSizeUploadHandler',
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

# Email configuration
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')
SERVER_EMAIL = os.environ.get('SERVER_EMAIL', DEFAULT_FROM_EMAIL)
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'False').lower() == 'true'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
FROM_MAIL = os.environ.get('FROM_MAIL', DEFAULT_FROM_EMAIL)
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
try:
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '25'))
except ValueError:
    EMAIL_PORT = None

# Frontend URLs
FRONTEND_URL = os.environ.get('FRONTEND_URL')
FRONTEND_RESET_URL = os.environ.get('FRONTEND_RESET_URL')
FRONTEND_VERIFY_EMAIL_URL = os.environ.get('FRONTEND_VERIFY_EMAIL_URL') or (
    f'{FRONTEND_URL.rstrip("/")}/auth/verify-email' if FRONTEND_URL else None
)

# API URLs
SELF_URL = os.environ.get('SELF_URL')

# Rest Framework
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'apps.generics.pagination.CustomPageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'apps.accounts.authentication.JWTCookieAuthentication',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '1000/hour',
        'user': '10000/hour',
        'auth': os.environ.get('AUTH_THROTTLE_RATE', '10/min'),
        'auth_refresh': os.environ.get('AUTH_REFRESH_THROTTLE_RATE', '60/min'),
    },
    'EXCEPTION_HANDLER': 'apps.generics.exceptions.custom_exception_handler',
    'NUM_PROXIES': (
        int(num_proxies) if (num_proxies := os.environ.get('NUM_PROXIES')) else None
    ),
}

# JWT Authentication settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=int(os.environ.get('ACCESS_TOKEN_LIFETIME', 15)),
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        minutes=int(os.environ.get('REFRESH_TOKEN_LIFETIME', 10080)),
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}
if jwt_signing_key := os.environ.get('JWT_SIGNING_KEY'):
    SIMPLE_JWT['SIGNING_KEY'] = jwt_signing_key

AUTH_TRANSPORT_HEADER = 'X-Auth-Transport'
AUTH_COOKIE_ACCESS_NAME = '__Host-access'
AUTH_COOKIE_REFRESH_NAME = '__Secure-refresh'
AUTH_COOKIE_REFRESH_PATH = '/api/auth/'
AUTH_COOKIE_SECURE = True
AUTH_COOKIE_SAMESITE = 'Lax'

# Drf Spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': gettext_lazy('CrewForge API'),
    'DESCRIPTION': gettext_lazy(
        """API service for managing accounts, teams, and permissions with comprehensive
        organizational hierarchy support.
        CrewForge provides a comprehensive foundation for building applications
        requiring sophisticated organizational structures, team management, and
        permission systems with enterprise-grade security and scalability.
    """
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',
    'SERVE_URLCONF': [
        'apps.accounts.urls',
        'apps.teams.urls',
    ],
    'ENUM_NAME_OVERRIDES': {
        'StoredFileAccess': 'apps.accounts.choices.StoredFileAccess',
    },
    'SERVE_PERMISSIONS': ['apps.generics.permissions.ApiDocsPermission'],
    'SERVE_AUTHENTICATION': [
        'apps.accounts.authentication.JWTCookieAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
}

API_DOCS_PUBLIC = (
    api_docs_public.lower() == 'true'
    if (api_docs_public := os.environ.get('API_DOCS_PUBLIC'))
    else None
)

ADMIN_URL = normalize_admin_url(os.environ.get('ADMIN_URL', 'admin/'))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'security': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'security': {
            'class': 'logging.StreamHandler',
            'formatter': 'security',
        },
    },
    'loggers': {
        'security': {
            'handlers': ['security'],
            'level': os.environ.get('SECURITY_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

CORS_ALLOWED_ORIGINS = []
if cors_origins := os.environ.get('CORS_ALLOWED_ORIGINS'):
    CORS_ALLOWED_ORIGINS = cors_origins.split(',')

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = (*default_cors_headers, AUTH_TRANSPORT_HEADER.lower())

SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SAMESITE = os.environ.get('CSRF_COOKIE_SAMESITE', 'Lax')

if session_domain := os.environ.get('SESSION_COOKIE_DOMAIN'):
    SESSION_COOKIE_DOMAIN = session_domain

if csrf_origins := os.environ.get('CSRF_TRUSTED_ORIGINS'):
    CSRF_TRUSTED_ORIGINS = csrf_origins.split(',')

# ─── Cookie / SameSite Validation ──────────────────────────────────────

if ENVIRONMENT == 'production' and (
    SESSION_COOKIE_SAMESITE == 'None' and not SESSION_COOKIE_SECURE
):
    raise ImproperlyConfigured(
        'SESSION_COOKIE_SAMESITE=None requires SESSION_COOKIE_SECURE=True. '
        'Cookies will be rejected by the browser.'
    )
elif (
    not DEBUG
    and not TESTING
    and (SESSION_COOKIE_SAMESITE == 'None' and not SESSION_COOKIE_SECURE)
):
    warnings.warn(
        'SECURITY WARNING: SESSION_COOKIE_SAMESITE=None requires '
        'SESSION_COOKIE_SECURE=True. Cookies will be rejected by the browser.',
        RuntimeWarning,
        stacklevel=2,
    )

# Celery
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_IGNORE_RESULT = (
    os.environ.get('CELERY_TASK_IGNORE_RESULT', 'False').lower() == 'true'
)

# System settings
SYSTEM_TITLE = os.environ.get('SYSTEM_TITLE', gettext_lazy('CrewForge'))
