from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import SAFE_METHODS

from apps.accounts.utils.security_log import log_security_event
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.services import record_audit_event
from apps.generics.errors import InvalidState
from apps.platform.choices import ImpersonationEndReasonChoices
from apps.platform.consts import (
    IMPERSONATION_DURATION_MINUTES,
    IMPERSONATION_SESSION_KEY,
)
from apps.platform.exceptions import ImpersonationEnded, ReadOnlyImpersonation
from apps.platform.models import Impersonation

ALLOWED_WRITES_WHILE_IMPERSONATING = frozenset(
    {
        'accounts:organizations-login',
        'accounts:logout',
        'platform:impersonation-exit',
    }
)

ENDED_MESSAGES = {
    ImpersonationEndReasonChoices.USER_BLOCKED: _(
        'The user was blocked, so the viewing session ended.'
    ),
}
DEFAULT_ENDED_MESSAGE = _('The viewing session ended.')


def _session(request):
    return getattr(request, 'session', None)


def _clear_session(request, impersonation_id: int) -> None:
    session = _session(request)
    if (
        session is not None
        and session.get(IMPERSONATION_SESSION_KEY) == impersonation_id
    ):
        session.pop(IMPERSONATION_SESSION_KEY, None)


def can_be_impersonated(staff, target) -> bool:
    return (
        target.pk != staff.pk
        and target.is_active
        and not target.is_blocked
        and not target.is_platform_staff
    )


@transaction.atomic
def start_impersonation(request, target, reason: str) -> Impersonation:
    staff = request.user
    if not can_be_impersonated(staff, target):
        raise InvalidState(
            _("This user can't be viewed (platform staff, blocked or deleted).")
        )
    for previous in Impersonation.objects.active().filter(staff=staff):
        if not previous.is_expired():
            raise InvalidState(_('You already have an active viewing session.'))
        end_impersonation(previous, ImpersonationEndReasonChoices.EXPIRED, request)
    now = timezone.now()
    impersonation = Impersonation.objects.create(
        staff=staff,
        target=target,
        reason=reason,
        started_at=now,
        expires_at=now + timedelta(minutes=IMPERSONATION_DURATION_MINUTES),
    )
    record_audit_event(
        AuditActionChoices.USER_IMPERSONATION_STARTED,
        request=request,
        target=target,
        metadata={'reason': reason},
        actor_type=AuditActorTypeChoices.PLATFORM,
        subject_user_id=target.pk,
    )
    session = _session(request)
    session.pop('organization_id', None)
    session[IMPERSONATION_SESSION_KEY] = impersonation.pk
    log_security_event(
        'impersonation.started',
        request,
        impersonation_id=impersonation.pk,
        target_user_id=target.pk,
    )
    return impersonation


@transaction.atomic
def end_impersonation(impersonation: Impersonation, end_reason: str, request=None):
    """End ``impersonation`` once; a concurrent end keeps the first reason."""
    locked = (
        Impersonation.objects.select_for_update()
        .select_related('staff', 'target')
        .get(pk=impersonation.pk)
    )
    if request is not None:
        _clear_session(request, locked.pk)
    if not locked.is_active:
        return locked
    locked.ended_at = timezone.now()
    locked.end_reason = end_reason
    locked.save(update_fields=['ended_at', 'end_reason'])
    expired = end_reason == ImpersonationEndReasonChoices.EXPIRED
    record_audit_event(
        AuditActionChoices.USER_IMPERSONATION_EXPIRED
        if expired
        else AuditActionChoices.USER_IMPERSONATION_ENDED,
        request=request,
        target=locked.target,
        metadata={'end_reason': end_reason},
        actor_type=AuditActorTypeChoices.PLATFORM,
        subject_user_id=locked.target_id,
        actor_user=locked.staff,
    )
    if request is not None:
        log_security_event(
            'impersonation.expired' if expired else 'impersonation.ended',
            request,
            impersonation_id=locked.pk,
            end_reason=end_reason,
        )
    return locked


def end_impersonations_of(target, end_reason: str, request=None) -> None:
    for impersonation in Impersonation.objects.active().filter(target=target):
        end_impersonation(impersonation, end_reason, request=request)


def ended_error(impersonation: Impersonation) -> ImpersonationEnded:
    return ImpersonationEnded(
        ENDED_MESSAGES.get(impersonation.end_reason, DEFAULT_ENDED_MESSAGE),
        details={'reason': impersonation.end_reason, 'user': impersonation.target_id},
    )


def resolve_impersonation(request, staff):
    """
    The target the request acts as, or ``None`` without an impersonation. An
    expired one, or one whose target was blocked meanwhile, is ended and refused.
    """
    session = _session(request)
    impersonation_id = session.get(IMPERSONATION_SESSION_KEY) if session else None
    if not impersonation_id:
        return None
    impersonation = (
        Impersonation.objects.select_related('target')
        .filter(pk=impersonation_id, staff=staff)
        .first()
    )
    if impersonation is None:
        session.pop(IMPERSONATION_SESSION_KEY, None)
        return None
    if not impersonation.is_active:
        session.pop(IMPERSONATION_SESSION_KEY, None)
        raise ended_error(impersonation)
    target = impersonation.target
    if impersonation.is_expired() or not staff.is_platform_staff:
        reason = ImpersonationEndReasonChoices.EXPIRED
    elif target.is_blocked or not target.is_active:
        reason = ImpersonationEndReasonChoices.USER_BLOCKED
    else:
        return impersonation
    raise ended_error(end_impersonation(impersonation, reason, request=request))


def refuse_writes_while_impersonating(request) -> None:
    if request.method in SAFE_METHODS:
        return
    match = getattr(request, 'resolver_match', None)
    if match is not None and match.view_name in ALLOWED_WRITES_WHILE_IMPERSONATING:
        return
    raise ReadOnlyImpersonation()
