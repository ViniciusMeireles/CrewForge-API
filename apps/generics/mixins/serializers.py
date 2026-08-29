import copy
from functools import lru_cache

from django.core.exceptions import FieldDoesNotExist
from django.db.models import ForeignObjectRel
from django.forms.utils import pretty_name
from django.utils.functional import classproperty
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.utils import model_meta

ORDERING_SEPARATOR = '__'
DESCENDING_PREFIX = '-'


def _deduplicate_preserve_order(fields: list[str]) -> list[str]:
    """Remove duplicates while preserving original order."""
    return list(dict.fromkeys(fields))


def _resolve_fields(cls: type[serializers.ModelSerializer]) -> list[str]:
    """Resolve the effective field list from Meta.fields or all model fields."""
    meta = getattr(cls, 'Meta', None)
    if meta is None:
        return list(getattr(cls, '_declared_fields', {}).keys())
    fields = getattr(meta, 'fields', None)
    if fields is None or fields == serializers.ALL_FIELDS:
        if getattr(meta, 'model', None) is None:
            return list(getattr(cls, '_declared_fields', {}).keys())
        return cls.all_model_fields
    return list(fields)


def _get_write_only_field_names(cls: type[serializers.Serializer]) -> set[str]:
    """Return field names marked as write_only for the serializer.

    Inspects the instantiated serializer fields which already merges
    ``Meta.extra_kwargs`` (e.g. ``password`` write_only) and declared
    fields. Falls back to declared fields if instantiation fails.
    """
    try:
        fields = cls().fields
    except Exception:
        return {
            name
            for name, field in cls._declared_fields.items()
            if getattr(field, 'write_only', False)
        }
    return {
        name for name, field in fields.items() if getattr(field, 'write_only', False)
    }


def _categorize_declared_fields(
    cls: type[serializers.Serializer],
    write_only_names: set[str],
) -> tuple[set[str], set[str]]:
    """Categorize declared fields into excluded and nested serializers.

    Excluded fields are ``SerializerMethodField`` or ``write_only`` and
    must not appear in ordering choices. Nested fields are
    ``BaseSerializer`` instances that can be expanded with a prefix
    (depth 1 only).
    """
    excluded: set[str] = set()
    nested: set[str] = set()
    for field_name, field in cls._declared_fields.items():
        if isinstance(field, serializers.SerializerMethodField):
            excluded.add(field_name)
            continue
        if field_name in write_only_names or getattr(field, 'write_only', False):
            excluded.add(field_name)
            continue
        if isinstance(field, serializers.BaseSerializer):
            nested.add(field_name)
    return excluded, nested


@lru_cache(maxsize=None)
def _ensure_orderable_serializer_class(
    serializer_class: type[serializers.Serializer],
) -> type[serializers.Serializer]:
    """Return a serializer class guaranteed to have ordering support.

    If the given class already inherits from ``ModelSerializerFieldsMixin``,
    it is returned unchanged. Otherwise a lightweight dynamic subclass is
    created to expose ``orderable_fields_choices`` without mutating the
    original class.
    """
    if issubclass(serializer_class, ModelSerializerFieldsMixin):
        return serializer_class
    return type(  # type: ignore
        f'Orderable{serializer_class.__name__}',
        (ModelSerializerFieldsMixin, serializer_class),
        {},
    )


def _interleave_descending(
    ascending: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Interleave ascending choices with their descending counterparts."""
    descending_label = _('Descending %(label)s')
    descending = [
        (f'{DESCENDING_PREFIX}{field}', descending_label % {'label': label})
        for field, label in ascending
    ]
    return [val for pair in zip(ascending, descending, strict=False) for val in pair]


class ModelSerializerFieldsMixin(serializers.ModelSerializer):
    @classproperty
    def all_model_fields(cls) -> list[str]:
        meta = getattr(cls, 'Meta', None)
        model = getattr(meta, 'model', None) if meta else None
        declared_fields = copy.deepcopy(getattr(cls, '_declared_fields', {}))

        model_info = model_meta.get_field_info(model)
        fields = (
            [model_info.pk.name]
            + list(declared_fields)
            + list(model_info.fields)
            + list(model_info.forward_relations)
        )
        if meta and (exclude := getattr(meta, 'exclude', None)):
            fields = [f for f in fields if f not in exclude]
        return fields

    @classmethod
    def _get_verbose_name_field(cls, field_name: str) -> str | None:
        verbose_name = _(pretty_name(field_name))
        meta = getattr(cls, 'Meta', None)
        if meta is None:
            return verbose_name
        model_class = getattr(meta, 'model', None)
        if not model_class:
            return verbose_name
        opts = model_class._meta
        field = opts.get_field(field_name)
        if isinstance(field, ForeignObjectRel):
            return None
        if field.verbose_name:
            return capfirst(field.verbose_name)
        return verbose_name

    @classmethod
    def _build_nested_choices(cls, field_name: str) -> list[tuple[str, str]]:
        """Build ordering choices for a nested serializer field (depth 1).

        Expands the nested serializer's own orderable choices with a
        ``field_name__`` prefix and keeps descending variants in sync.
        Already-prefixed choices are skipped to enforce a single level of
        nesting.

        Args:
            field_name: Declared field name holding a ``BaseSerializer``.

        Returns:
            List of ``(value, label)`` tuples, e.g. ``user__email``.
        """
        try:
            verbose_name = cls._get_verbose_name_field(field_name)
        except FieldDoesNotExist:
            return []
        if verbose_name is None:
            verbose_name = capfirst(_(pretty_name(field_name)))

        field = cls._declared_fields.get(field_name)
        if field is None:
            return []

        serializer_class = field.__class__
        serializer_class = _ensure_orderable_serializer_class(serializer_class)

        choices: list[tuple[str, str]] = []
        try:
            nested_choices = serializer_class.orderable_fields_choices
        except AttributeError, FieldDoesNotExist:
            return []
        for sub_field, sub_label in nested_choices:
            # Enforce depth 1: skip choices that are already nested.
            if ORDERING_SEPARATOR in sub_field.lstrip(DESCENDING_PREFIX):
                continue
            is_descending = sub_field.startswith(DESCENDING_PREFIX)
            if is_descending:
                value = (
                    f'{DESCENDING_PREFIX}{field_name}{ORDERING_SEPARATOR}'
                    f'{sub_field[1:]}'
                )
            else:
                value = f'{field_name}{ORDERING_SEPARATOR}{sub_field}'
            label = f'{verbose_name} - {sub_label}'
            choices.append((value, label))
        return choices

    @classproperty
    def orderable_fields_choices(cls) -> list[tuple[str, str]]:
        """Return ordering choices for ``OrderingFilter`` including nested fields.

        Combines own model fields (sorted by verbose name, interleaved
        ascending/descending) with a trailing block of nested serializer
        choices at depth 1. Write-only fields from both declared and model
        ``extra_kwargs`` are excluded at both levels.
        """
        fields = _deduplicate_preserve_order(_resolve_fields(cls))
        write_only_names = _get_write_only_field_names(cls)
        excluded, nested = _categorize_declared_fields(cls, write_only_names)

        # Merge write-only model fields into the excluded set for own fields.
        excluded = excluded | write_only_names

        own_choices: list[tuple[str, str]] = []
        nested_choices: list[tuple[str, str]] = []

        for field_name in fields:
            if field_name in excluded:
                continue
            try:
                verbose_name = cls._get_verbose_name_field(field_name)
            except FieldDoesNotExist:
                continue
            if field_name in nested:
                nested_choices.extend(cls._build_nested_choices(field_name))
            elif verbose_name:
                own_choices.append((field_name, verbose_name))

        ascending = sorted(own_choices, key=lambda x: x[1])
        interleaved = _interleave_descending(ascending)
        return interleaved + nested_choices
