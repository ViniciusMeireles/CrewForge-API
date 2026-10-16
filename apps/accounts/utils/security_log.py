import logging

from apps.audit.choices import AuditActionChoices
from apps.audit.services import record_audit_event
from apps.generics.utils.requests import client_ip

logger = logging.getLogger('security')

__all__ = ['client_ip', 'log_security_event']

PRIVATE_FIELDS = frozenset({'email', 'username', 'password', 'token'})


def log_security_event(
    event: str,
    request,
    user_id: int | None = None,
    level: int = logging.INFO,
    audit: dict | None = None,
    **fields,
) -> None:
    """
    Log a security event without credentials, tokens or emails and store it as an
    audit event when ``event`` is an ``AuditActionChoices`` value. ``audit`` holds
    extra ``record_audit_event`` arguments (target, changes, actor_member) that
    never reach the log line.
    """
    event = str(event)
    if user_id is None and (user := getattr(request, 'user', None)):
        user_id = user.pk if user.is_authenticated else None
    data = {'event': event, 'user_id': user_id, 'ip': client_ip(request), **fields}
    message = ' '.join(
        f'{key}={value}' for key, value in data.items() if value is not None
    )
    logger.log(level, message, extra={'security_event': data})
    if event in AuditActionChoices.values:
        _persist(event, request, user_id, fields, audit or {})


def _persist(event: str, request, user_id, fields: dict, audit: dict) -> None:
    metadata = {
        key: value
        for key, value in fields.items()
        if key not in PRIVATE_FIELDS and key != 'organization_id'
    }
    kwargs = {'subject_user_id': user_id, 'metadata': metadata, **audit}
    record_audit_event(
        event,
        request=request,
        organization_id=fields.get('organization_id'),
        **kwargs,
    )
