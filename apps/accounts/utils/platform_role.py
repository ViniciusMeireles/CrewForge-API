from django.db import transaction

from apps.accounts.choices import PlatformRoleChoices
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.services import record_audit_event


def set_platform_role(user, role: str, *, request=None) -> bool:
    role = PlatformRoleChoices(role)
    previous = user.platform_role
    if previous == role:
        return False
    with transaction.atomic():
        user.platform_role = role
        user.save(update_fields=['platform_role', 'updated_at'])
        record_audit_event(
            AuditActionChoices.USER_PLATFORM_ROLE_CHANGED,
            request=request,
            target=user,
            subject_user_id=user.pk,
            changes=[{'field': 'platform_role', 'before': previous, 'after': role}],
            actor_type=AuditActorTypeChoices.PLATFORM
            if request is not None
            else AuditActorTypeChoices.SYSTEM,
        )
    return True
