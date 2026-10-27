from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.choices import MemberRoleChoices, OrganizationStatusChoices
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.accounts.utils.email_verification import (
    send_verification_email,
    verification_cooldown_remaining,
)
from apps.accounts.utils.language import resolve_recipient_language
from apps.accounts.utils.password_reset import password_reset_link
from apps.accounts.utils.sessions import revoke_sessions
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.services import label_for, record_audit_event
from apps.generics.errors import CooldownThrottled, InvalidState
from apps.generics.utils.db import queue_on_commit
from apps.platform.choices import ImpersonationEndReasonChoices
from apps.platform.impersonation import end_impersonations_of

User = get_user_model()


def _reason_metadata(reason: str) -> dict:
    return {'reason': reason} if reason else {}


def _ref(instance) -> dict | None:
    return {'id': instance.pk, 'label': label_for(instance)} if instance else None


def _record_organization_event(request, action, organization, reason, changes=()):
    record_audit_event(
        action,
        request=request,
        organization_id=organization.pk,
        target=organization,
        changes=changes,
        metadata=_reason_metadata(reason),
        actor_type=AuditActorTypeChoices.PLATFORM,
    )


def _record_account_event(request, action, user, reason, changes=()):
    record_audit_event(
        action,
        request=request,
        target=user,
        changes=changes,
        metadata=_reason_metadata(reason),
        actor_type=AuditActorTypeChoices.PLATFORM,
        subject_user_id=user.pk,
    )


def _queue_organization_notice(email_class_name: str, user, **kwargs) -> None:
    """Email ``user`` after the commit; the action never waits for or fails on it."""
    from apps.accounts.tasks import send_organization_notice_email

    if user is None or not user.email:
        return
    email = user.email
    language = resolve_recipient_language(user)
    queue_on_commit(
        lambda: send_organization_notice_email(
            email_class_name, [email], kwargs, language=language
        ),
        f'{email_class_name} for user {user.pk}',
    )


def _locked_organization(organization_id: int) -> Organization:
    return (
        Organization.objects.select_for_update(of=('self',))
        .select_related('owner__user')
        .get(pk=organization_id)
    )


def _locked_user(user_id: int):
    """The target of an account action; deleted accounts are refused."""
    user = User.objects.select_for_update().get(pk=user_id)
    if not user.is_active:
        raise InvalidState(_('This user account is deleted.'))
    return user


@transaction.atomic
def suspend_organization(request, organization: Organization, reason: str):
    organization = _locked_organization(organization.pk)
    if organization.is_suspended:
        raise InvalidState(_('This organization is already suspended.'))
    organization.status = OrganizationStatusChoices.SUSPENDED
    organization.suspended_at = timezone.now()
    organization.suspended_by = request.user
    organization.suspension_reason = reason
    organization.save(
        update_fields=[
            'status',
            'suspended_at',
            'suspended_by',
            'suspension_reason',
            'updated_at',
        ]
    )
    _record_organization_event(
        request,
        AuditActionChoices.ORGANIZATION_SUSPENDED,
        organization,
        reason,
        changes=[{'field': 'status', 'before': 'active', 'after': 'suspended'}],
    )
    owner = organization.owner.user if organization.owner else None
    _queue_organization_notice(
        'OrganizationSuspendedEmail', owner, organization_name=organization.name
    )
    return organization


@transaction.atomic
def reactivate_organization(request, organization: Organization, reason: str = ''):
    organization = _locked_organization(organization.pk)
    if not organization.is_suspended:
        raise InvalidState(_('This organization is already active.'))
    organization.status = OrganizationStatusChoices.ACTIVE
    organization.suspended_at = None
    organization.suspended_by = None
    organization.suspension_reason = ''
    organization.save(
        update_fields=[
            'status',
            'suspended_at',
            'suspended_by',
            'suspension_reason',
            'updated_at',
        ]
    )
    _record_organization_event(
        request,
        AuditActionChoices.ORGANIZATION_REACTIVATED,
        organization,
        reason,
        changes=[{'field': 'status', 'before': 'suspended', 'after': 'active'}],
    )
    owner = organization.owner.user if organization.owner else None
    _queue_organization_notice(
        'OrganizationReactivatedEmail', owner, organization_name=organization.name
    )
    return organization


@transaction.atomic
def transfer_ownership(
    request, organization: Organization, member: Member, reason: str
):
    """New owner becomes Owner, the previous one Admin, all or nothing (BR-18)."""
    organization = _locked_organization(organization.pk)
    new_owner = (
        Member.objects.select_for_update(of=('self',))
        .select_related('user')
        .filter_actives()
        .filter(pk=member.pk, organization=organization)
        .exclude(pk=organization.owner_id)
        .first()
    )
    if new_owner is None:
        raise InvalidState(_('This member can no longer become the owner.'))
    previous_owner = organization.owner
    changes = [
        {'field': 'owner', 'before': _ref(previous_owner), 'after': _ref(new_owner)},
    ]
    if previous_owner is not None:
        changes.append(
            {
                'field': 'previous_owner_role',
                'before': previous_owner.role,
                'after': MemberRoleChoices.ADMIN,
            }
        )
        previous_owner.role = MemberRoleChoices.ADMIN
        previous_owner.save(update_fields=['role', 'updated_at'])
    changes.append(
        {
            'field': 'new_owner_role',
            'before': new_owner.role,
            'after': MemberRoleChoices.OWNER,
        }
    )
    new_owner.role = MemberRoleChoices.OWNER
    new_owner.save(update_fields=['role', 'updated_at'])
    organization.owner = new_owner
    organization.save(update_fields=['owner', 'updated_at'])
    _record_organization_event(
        request,
        AuditActionChoices.ORGANIZATION_OWNERSHIP_TRANSFERRED,
        organization,
        reason,
        changes=changes,
    )
    _queue_organization_notice(
        'OwnershipTransferredNewOwnerEmail',
        new_owner.user,
        organization_name=organization.name,
    )
    if previous_owner is not None:
        _queue_organization_notice(
            'OwnershipTransferredPreviousOwnerEmail',
            previous_owner.user,
            organization_name=organization.name,
            new_owner_name=label_for(new_owner.user),
        )
    return organization


@transaction.atomic
def block_user(request, user, reason: str):
    if user.pk == request.user.pk:
        raise InvalidState(_("You can't block your own account."))
    user = _locked_user(user.pk)
    if user.is_blocked:
        raise InvalidState(_('This user is already blocked.'))
    user.blocked_at = timezone.now()
    user.blocked_by = request.user
    user.blocked_reason = reason
    user.save(
        update_fields=['blocked_at', 'blocked_by', 'blocked_reason', 'updated_at']
    )
    revoke_sessions(user)
    end_impersonations_of(user, ImpersonationEndReasonChoices.USER_BLOCKED)
    _record_account_event(request, AuditActionChoices.USER_BLOCKED, user, reason)
    return user


@transaction.atomic
def unblock_user(request, user, reason: str = ''):
    """Allow signing in again; sessions ended by the block stay ended (BR-23)."""
    user = _locked_user(user.pk)
    if not user.is_blocked:
        raise InvalidState(_('This user is not blocked.'))
    user.blocked_at = None
    user.blocked_by = None
    user.blocked_reason = ''
    user.save(
        update_fields=['blocked_at', 'blocked_by', 'blocked_reason', 'updated_at']
    )
    _record_account_event(request, AuditActionChoices.USER_UNBLOCKED, user, reason)
    return user


@transaction.atomic
def end_sessions(request, user, reason: str = ''):
    user = _locked_user(user.pk)
    revoke_sessions(user)
    _record_account_event(request, AuditActionChoices.USER_SESSIONS_ENDED, user, reason)
    return user


@transaction.atomic
def resend_verification(request, user, reason: str = ''):
    user = _locked_user(user.pk)
    if user.email_verified:
        raise InvalidState(_("This user's email is already verified."))
    if not send_verification_email(user):
        seconds = verification_cooldown_remaining(user)
        raise CooldownThrottled(
            _('Wait {seconds} seconds before sending again.').format(seconds=seconds),
            retry_after_seconds=seconds,
        )
    _record_account_event(
        request, AuditActionChoices.USER_VERIFICATION_RESENT, user, reason
    )
    return user


@transaction.atomic
def force_password_reset(request, user, reason: str = ''):
    """The current password stops working, sessions end, a reset link is emailed."""
    from apps.accounts.tasks import send_password_reset_email

    user = _locked_user(user.pk)
    user.set_unusable_password()
    user.save(update_fields=['password', 'updated_at'])
    revoke_sessions(user)
    reset_link = password_reset_link(user)
    email = user.email
    language = resolve_recipient_language(user)
    queue_on_commit(
        lambda: send_password_reset_email(reset_link, [email], language=language),
        f'the password reset for user {user.pk}',
    )
    _record_account_event(
        request, AuditActionChoices.USER_PASSWORD_RESET_FORCED, user, reason
    )
    return user
