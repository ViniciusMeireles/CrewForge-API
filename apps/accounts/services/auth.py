from typing import Any

from django.db import transaction
from rest_framework.request import Request

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization, OrganizationProfile
from apps.accounts.models.user import User
from apps.accounts.utils.email_verification import (
    mark_email_verified,
    send_verification_email,
)
from apps.accounts.utils.language import resolve_recipient_language
from apps.accounts.utils.password_reset import password_reset_link
from apps.accounts.utils.security_log import log_security_event
from apps.accounts.utils.sessions import revoke_sessions


def _create_user(user_data: dict[str, Any]) -> User:
    user = User(**user_data)
    user.set_password(user_data.get('password'))
    user.save()
    user.created_by = user
    user.updated_by = user
    user.save(update_fields=['created_by', 'updated_by'])
    return user


def register_owner(
    *,
    user_data: dict[str, Any],
    organization_data: dict[str, Any],
    member_data: dict[str, Any],
) -> Member:
    with transaction.atomic():
        user = _create_user(user_data)
        send_verification_email(user)
        profile_data = organization_data.pop('profile', None) or {}
        organization = Organization.objects.create(
            created_by=user,
            updated_by=user,
            **organization_data,
        )
        OrganizationProfile.objects.create(
            organization=organization,
            created_by=user,
            updated_by=user,
            **profile_data,
        )
        return Member.objects.create(
            **{
                'role': MemberRoleChoices.OWNER,
                **member_data,
                'user': user,
                'organization': organization,
                'created_by': user,
                'updated_by': user,
            }
        )


def record_signup(*, request: Request, user_id: int | None, **fields: Any) -> None:
    log_security_event('auth.signup', request, user_id=user_id, **fields)


def request_password_reset(
    *, user: User | None, request: Request | None = None
) -> None:
    from apps.accounts.tasks import send_password_reset_email

    if user:
        send_password_reset_email(
            password_reset_link(user),
            [user.email],
            language=resolve_recipient_language(user),
        )
    log_security_event(
        'auth.password_reset.requested',
        request,
        user_id=user.pk if user else None,
    )


def confirm_password_reset(
    *, user: User, new_password: str, request: Request | None = None
) -> None:
    user.set_password(new_password)
    user.save()
    revoke_sessions(user)
    log_security_event('auth.password_reset.completed', request, user_id=user.pk)


def change_password(
    *, user: User, new_password: str, request: Request | None = None
) -> None:
    user.set_password(new_password)
    user.save(update_fields=['password'])
    revoke_sessions(user)
    log_security_event('auth.password.changed', request, user_id=user.pk)


def verify_email(*, user: User, request: Request | None = None) -> None:
    mark_email_verified(user)
    log_security_event('auth.email.verified', request, user_id=user.pk)
