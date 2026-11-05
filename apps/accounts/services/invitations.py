from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.request import Request

from apps.accounts.choices import InvitationStatusChoices
from apps.accounts.consts import INVITATION_EMAIL_COOLDOWN_SECONDS
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.accounts.models.user import User
from apps.accounts.selectors.invitations import lock_invitation
from apps.accounts.utils.security_log import log_security_event
from apps.audit.choices import AuditActionChoices
from apps.audit.services import record_audit_event

type InvitationCheck = Callable[[Invitation], None]


class InvitationRefusedError(ValueError):
    pass


class InvitationEmailCooldownError(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(retry_after)
        self.retry_after = retry_after


@dataclass(frozen=True)
class AcceptedInvitation:
    invitation: Invitation
    member: Member
    readmitted: bool


def expire_stale_invitations(*, organization: Organization | None, email: str) -> None:
    Invitation.objects.filter(
        organization=organization,
        email__iexact=email,
        status=InvitationStatusChoices.PENDING,
        expired_at__lte=timezone.now(),
    ).update(status=InvitationStatusChoices.EXPIRED)


def send_invitation_on_commit(invitation: Invitation) -> None:
    if invitation.is_acceptable()[0]:
        transaction.on_commit(invitation.send_email)


def resend_invitation_email(
    *, invitation: Invitation, request: Request | None = None
) -> None:
    is_acceptable, message = invitation.is_acceptable()
    if not is_acceptable:
        raise InvitationRefusedError(message)
    if invitation.last_email_sent_at:
        elapsed = (timezone.now() - invitation.last_email_sent_at).total_seconds()
        if elapsed < INVITATION_EMAIL_COOLDOWN_SECONDS:
            raise InvitationEmailCooldownError(
                int(INVITATION_EMAIL_COOLDOWN_SECONDS - elapsed)
            )
    with transaction.atomic():
        transaction.on_commit(invitation.send_email)
        invitation.last_email_sent_at = timezone.now()
        invitation.save(update_fields=['last_email_sent_at', 'updated_at'])
        record_audit_event(
            AuditActionChoices.INVITATION_EMAIL_SENT,
            request=request,
            target=invitation,
        )


def _member_audit(member: Member) -> dict[str, Any]:
    return {
        'target': member,
        'changes': [{'field': 'role', 'before': None, 'after': member.role}],
    }


def _record_acceptance(
    invitation: Invitation,
    member: Member,
    readmitted: bool,
    request: Request | None,
) -> None:
    logged, audited = (
        (
            AuditActionChoices.MEMBER_READMITTED,
            AuditActionChoices.INVITATION_ACCEPTED,
        )
        if readmitted
        else (
            AuditActionChoices.INVITATION_ACCEPTED,
            AuditActionChoices.MEMBER_JOINED,
        )
    )
    targets: dict[str, dict[str, Any]] = {
        AuditActionChoices.INVITATION_ACCEPTED: {'target': invitation},
        AuditActionChoices.MEMBER_READMITTED: _member_audit(member),
        AuditActionChoices.MEMBER_JOINED: _member_audit(member),
    }
    log_security_event(
        logged,
        request,
        invitation_id=invitation.pk,
        organization_id=invitation.organization_id,
        member_id=member.pk,
        audit={'actor_member': member, **targets[logged]},
    )
    record_audit_event(
        audited,
        request=request,
        organization_id=invitation.organization_id,
        actor_member=member,
        metadata={'invitation_id': invitation.pk, 'member_id': member.pk},
        **targets[audited],
    )


def accept_invitation(
    *,
    invitation_pk: str,
    user: User,
    check: InvitationCheck,
    nickname: str = '',
    request: Request | None = None,
) -> AcceptedInvitation:
    with transaction.atomic():
        invitation = lock_invitation(invitation_pk=invitation_pk)
        check(invitation)
        invitation.ensure_organization_not_suspended()
        is_acceptable, message = invitation.is_acceptable()
        if not is_acceptable:
            raise InvitationRefusedError(message)
        member, readmitted = Member.objects.admit(
            user=user,
            organization=invitation.organization,
            role=invitation.role,
            nickname=nickname,
        )
        invitation.accept(member=member, check=False)
        _record_acceptance(invitation, member, readmitted, request)
    return AcceptedInvitation(invitation, member, readmitted)


def decline_invitation(
    *,
    invitation_pk: str,
    user: User,
    check: InvitationCheck,
    request: Request | None = None,
) -> Invitation:
    with transaction.atomic():
        invitation = lock_invitation(invitation_pk=invitation_pk)
        check(invitation)
        is_declinable, message = invitation.is_declinable()
        if not is_declinable:
            raise InvitationRefusedError(message)
        invitation.decline(user=user, check=False)
        record_audit_event(
            AuditActionChoices.INVITATION_DECLINED,
            request=request,
            organization_id=invitation.organization_id,
            target=invitation,
        )
    return invitation
