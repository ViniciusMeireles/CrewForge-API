from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver

from apps.platform.choices import ImpersonationEndReasonChoices
from apps.platform.impersonation import end_impersonation


@receiver(user_logged_out)
def end_impersonation_on_sign_out(sender, request, **kwargs):
    if impersonation := getattr(request, 'impersonation', None):
        end_impersonation(
            impersonation, ImpersonationEndReasonChoices.SIGNED_OUT, request=request
        )
