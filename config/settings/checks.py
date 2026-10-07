from django.core.exceptions import ImproperlyConfigured

MIN_SECRET_LENGTH = 50
DEVELOPMENT_ENVIRONMENTS = frozenset({'local_development', 'devcontainer', 'test'})
INSECURE_PREFIX = 'django-insecure'


def require_secret(name: str, value: str | None) -> str:
    if not value:
        raise ImproperlyConfigured(f'{name} must be set.')
    if len(value) < MIN_SECRET_LENGTH:
        raise ImproperlyConfigured(
            f'{name} must have at least {MIN_SECRET_LENGTH} characters.'
        )
    if value.startswith(INSECURE_PREFIX):
        raise ImproperlyConfigured(f'{name} must not be a development key.')
    return value
