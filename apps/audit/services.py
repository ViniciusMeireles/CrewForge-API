import datetime
import decimal
import uuid

from django.apps import apps
from django.db import models

from apps.accounts.utils.requests import get_member, get_organization_id
from apps.audit.choices import ACCOUNT_ACTION_PREFIXES, AuditActorTypeChoices
from apps.audit.models.audit_event import AuditEvent
from apps.generics.utils.requests import client_ip

SENSITIVE_FIELDS = frozenset({'password', 'key', 'token', 'last_login', 'session_key'})
BOOKKEEPING_FIELDS = frozenset(
    {'id', 'created_at', 'updated_at', 'created_by', 'updated_by'}
)


def label_for(obj) -> str:
    """Readable label (``audit_label``, then ``full_name``, then ``str``)."""
    if obj is None:
        return ''
    label = getattr(obj, 'audit_label', None) or getattr(obj, 'full_name', None) or obj
    return str(label)[:300]


def model_target_type(model: type[models.Model]) -> str:
    """Snake-case model name, e.g. ``team_member``."""
    name = model.__name__
    return ''.join(f'_{c.lower()}' if c.isupper() else c for c in name).lstrip('_')


def target_type_for(instance) -> str:
    return model_target_type(type(instance))


def model_for_target_type(target_type: str) -> type[models.Model] | None:
    """Model whose ``model_target_type`` is ``target_type`` (local apps only)."""
    for model in apps.get_models():
        if model.__module__.startswith('apps.') and (
            model_target_type(model) == target_type
        ):
            return model
    return None


def _audited_fields(instance, exclude=()) -> list[models.Field]:
    skipped = SENSITIVE_FIELDS | BOOKKEEPING_FIELDS | set(exclude)
    return [
        field
        for field in instance._meta.concrete_fields
        if field.name not in skipped and not getattr(field, 'generated', False)
    ]


def _display_value(instance, field: models.Field):
    if field.is_relation:
        related = getattr(instance, field.name, None)
        return {'id': related.pk, 'label': label_for(related)} if related else None
    value = getattr(instance, field.attname)
    if isinstance(value, models.fields.files.FieldFile):
        return value.name or None
    if isinstance(value, datetime.date | datetime.time):
        return value.isoformat()
    if isinstance(value, decimal.Decimal | uuid.UUID):
        return str(value)
    return value


def snapshot_instance(instance, exclude=()) -> dict:
    """Audited field values of ``instance`` in a JSON-friendly form."""
    return {
        field.name: _display_value(instance, field)
        for field in _audited_fields(instance, exclude)
    }


def diff_instance(before: dict, instance, exclude=()) -> list[dict]:
    """Changed fields between ``before`` and the current state of ``instance``."""
    after = snapshot_instance(instance, exclude)
    return [
        {'field': name, 'before': before.get(name), 'after': value}
        for name, value in after.items()
        if before.get(name) != value
    ]


def is_account_action(action: str) -> bool:
    return action.startswith(ACCOUNT_ACTION_PREFIXES)


def _request_user(request):
    user = getattr(request, 'user', None)
    return user if user is not None and user.is_authenticated else None


def _actor_fields(request, organization_id, actor_member) -> dict:
    """Actor of the event; a session Member of another organization is ignored."""
    user = _request_user(request)
    member = actor_member
    if member is None and user is not None and organization_id is not None:
        member = get_member(request)
        member = (
            member if member and member.organization_id == organization_id else None
        )
    user = user or (member.user if member else None)
    return {
        'actor_user': user,
        'actor_member': member,
        'actor_label': label_for(member or user),
        'ip': client_ip(request) if request is not None else None,
        'impersonator': getattr(request, 'impersonator', None),
    }


def _organization_id(action, request, target, organization_id):
    if is_account_action(action):
        return None
    if organization_id is not None:
        return organization_id
    if target is not None and getattr(target, 'organization_id', None):
        return target.organization_id
    return get_organization_id(request) if request is not None else None


def _target_fields(target, target_type, target_id, target_label) -> dict:
    return {
        'target_type': target_type or (target_type_for(target) if target else ''),
        'target_id': str(target_id or (target.pk if target else '') or ''),
        'target_label': target_label or label_for(target),
    }


def _actor_type(actor: dict, subject_user_id) -> str:
    if actor['actor_user'] or subject_user_id:
        return AuditActorTypeChoices.USER
    return AuditActorTypeChoices.SYSTEM


def record_audit_event(
    action: str,
    *,
    request=None,
    organization_id: int | None = None,
    target=None,
    target_type: str = '',
    target_id=None,
    target_label: str = '',
    changes=(),
    metadata: dict | None = None,
    actor_type: str | None = None,
    actor_member=None,
    subject_user_id: int | None = None,
) -> AuditEvent:
    """Store one audit event; errors propagate to roll back the caller."""
    organization_id = _organization_id(action, request, target, organization_id)
    actor = _actor_fields(request, organization_id, actor_member)
    if is_account_action(action) and subject_user_id is None and actor['actor_user']:
        subject_user_id = actor['actor_user'].pk
    return AuditEvent.objects.create(
        action=action,
        actor_type=actor_type or _actor_type(actor, subject_user_id),
        organization_id=organization_id,
        subject_user_id=subject_user_id,
        changes=list(changes),
        metadata=metadata or {},
        **actor,
        **_target_fields(target, target_type, target_id, target_label),
    )
