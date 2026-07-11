from celery import shared_task
from django.utils.module_loading import import_string


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    ignore_result=True,
)
def send_email(self, email_class_path: str, recipient_list: list[str], kwargs: dict):
    email_class = import_string(email_class_path)
    email = email_class(recipient_list=recipient_list, **kwargs)
    email.send(fail_silently=False)
