import logging
import socket
from smtplib import SMTPConnectError

from celery import shared_task
from django.conf import settings
from django.utils import translation
from django.utils.module_loading import import_string

from apps.generics.mails.bases import EmailBase

logger = logging.getLogger(__name__)

ALLOWED_EMAIL_MODULES = ('apps.accounts.emails.',)


@shared_task(
    bind=True,
    autoretry_for=(SMTPConnectError, ConnectionRefusedError, socket.gaierror),
    retry_backoff=True,
    max_retries=3,
    ignore_result=True,
)
def send_email(
    self,
    email_class_path: str,
    recipient_list: list[str],
    kwargs: dict,
    language: str | None = None,
):
    if not email_class_path.startswith(ALLOWED_EMAIL_MODULES):
        logger.error('Refused email class %s', email_class_path)
        return
    email_class = import_string(email_class_path)
    if not (isinstance(email_class, type) and issubclass(email_class, EmailBase)):
        logger.error('Refused email class %s', email_class_path)
        return
    with translation.override(language or settings.LANGUAGE_CODE):
        email = email_class(recipient_list=recipient_list, **kwargs)
        email.send(fail_silently=False)
