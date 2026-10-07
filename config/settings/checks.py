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


def require_production_secrets(secret_key: str | None, simple_jwt: dict) -> str:
    require_secret('DJANGO_SECRET_KEY', secret_key)
    if 'SIGNING_KEY' in simple_jwt:
        require_secret('JWT_SIGNING_KEY', simple_jwt['SIGNING_KEY'])
    return secret_key
