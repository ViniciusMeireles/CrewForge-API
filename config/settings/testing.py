from .local import *  # noqa

CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_IGNORE_RESULT = True

# Uploaded files live in memory during tests: nothing is written to MEDIA_ROOT.
STORAGES = {
    **STORAGES,  # noqa: F405
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
}

REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_THROTTLE_RATES': {
        **REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'],  # noqa: F405
        'auth': '10000/min',
        'auth_refresh': '10000/min',
    },
}

LOGGING = {
    **LOGGING,  # noqa: F405
    'handlers': {'security': {'class': 'logging.NullHandler'}},
}
