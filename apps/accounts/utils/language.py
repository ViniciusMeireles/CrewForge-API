from django.contrib.auth import get_user_model
from django.utils.translation import get_language


def normalize_language(value: str | None) -> str:
    if value and value.lower().startswith('pt'):
        return 'pt-br'
    return 'en'


def current_language() -> str:
    return normalize_language(get_language())


def resolve_recipient_language(user=None) -> str:
    if user is None:
        return current_language()
    return normalize_language(user.preferred_language)


def resolve_invitation_language(email: str) -> str:
    User = get_user_model()
    row = User.objects.filter(email__iexact=email).values('preferred_language').first()
    if row is None:
        return current_language()
    return normalize_language(row['preferred_language'])
