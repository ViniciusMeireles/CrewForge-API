from django.utils.translation import get_language

from apps.generics.tasks import send_email as send_email_task


def send_password_reset_email(
    reset_url: str, recipient_list: list[str], language: str | None = None
):
    send_email_task.apply_async(
        kwargs=dict(
            email_class_path='apps.accounts.emails.PasswordResetRequestEmail',
            recipient_list=recipient_list,
            kwargs={'reset_url': reset_url},
            language=language or get_language(),
        ),
        countdown=1,
    )


def send_invitation_email(
    invitation_id: int, recipient_list: list[str], language: str | None = None
):
    send_email_task.apply_async(
        kwargs=dict(
            email_class_path='apps.accounts.emails.InvitationEmail',
            recipient_list=recipient_list,
            kwargs={'invitation': invitation_id},
            language=language or get_language(),
        ),
        countdown=1,
    )


def send_email_verification_email(
    verify_url: str, recipient_list: list[str], language: str | None = None
):
    send_email_task.apply_async(
        kwargs=dict(
            email_class_path='apps.accounts.emails.EmailVerificationEmail',
            recipient_list=recipient_list,
            kwargs={'verify_url': verify_url},
            language=language or get_language(),
        ),
        countdown=1,
    )
