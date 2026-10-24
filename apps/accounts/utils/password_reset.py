from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def password_reset_uid_token(user) -> tuple[str, str]:
    return (
        urlsafe_base64_encode(force_bytes(user.pk)),
        default_token_generator.make_token(user),
    )


def password_reset_link(user) -> str:
    uid, token = password_reset_uid_token(user)
    return f'{settings.FRONTEND_RESET_URL}?uid={uid}&token={token}'
