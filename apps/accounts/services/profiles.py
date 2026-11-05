from collections.abc import Callable
from typing import Any

from django.db import transaction
from rest_framework.request import Request

from apps.accounts.models.user import User
from apps.accounts.utils.email_verification import send_verification_email
from apps.audit.choices import AuditActionChoices
from apps.audit.services import diff_instance, record_audit_event, snapshot_instance

PROFILE_AUDIT_EXCLUDE = (
    'password',
    'email',
    'email_verified_at',
    'email_verification_sent_at',
    'is_staff',
    'is_superuser',
    'date_joined',
)


def update_profile(
    *, user: User, save: Callable[[], Any], request: Request | None = None
) -> None:
    with transaction.atomic():
        before = snapshot_instance(user, PROFILE_AUDIT_EXCLUDE)
        email = user.email
        save()
        email_changed = user.email != email
        if email_changed:
            send_verification_email(user)
        changes = diff_instance(before, user, PROFILE_AUDIT_EXCLUDE)
        if email_changed:
            changes.append({'field': 'email', 'before': None, 'after': None})
        if changes:
            record_audit_event(
                AuditActionChoices.USER_PROFILE_UPDATED,
                request=request,
                target=user,
                changes=changes,
                metadata={'email_changed': True} if email_changed else {},
            )
