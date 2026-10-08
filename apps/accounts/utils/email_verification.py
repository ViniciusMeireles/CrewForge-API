import logging

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = 'apps.accounts.utils.email_verification.EmailVerificationTokenGenerator'

    def _make_hash_value(self, user, timestamp):
        return f'{user.pk}{user.email}{user.email_verified_at}{timestamp}'


email_verification_token = EmailVerificationTokenGenerator()


def verification_url(user) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    return f'{settings.FRONTEND_VERIFY_EMAIL_URL}?uid={uid}&token={token}'


def send_verification_email(user) -> None:
    from apps.accounts.tasks import send_email_verification_email

    url = verification_url(user)
    email = user.email

    def send():
        try:
            send_email_verification_email(url, [email])
        except Exception:
            logger.exception(
                'Could not queue the email verification for user %s', user.pk
            )

    transaction.on_commit(send)


def mark_email_verified(user) -> None:
    user.email_verified_at = timezone.now()
    user.save(update_fields=['email_verified_at', 'updated_at'])
