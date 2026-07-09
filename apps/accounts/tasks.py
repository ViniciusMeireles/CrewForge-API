from apps.generics.tasks import send_email as send_email_task


def send_password_reset_email(reset_url: str, recipient_list: list[str]):
    send_email_task.delay(
        email_class_path='apps.accounts.emails.PasswordResetRequestEmail',
        recipient_list=recipient_list,
        kwargs={'reset_url': reset_url},
    )


def send_invitation_email(invitation_id: int, recipient_list: list[str]):
    send_email_task.delay(
        email_class_path='apps.accounts.emails.InvitationEmail',
        recipient_list=recipient_list,
        kwargs={'invitation': invitation_id},
    )
