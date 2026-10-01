"""
Serializers that describe the selectable fields of a write serializer.

An options serializer is generated per ViewSet action (see
``OptionsBaseModelMixin``) with ``Meta.serializer_class`` pointing to the source
write serializer. Only fields the write endpoint accepts as a choice or a PK are
exposed.
"""

import copy
from functools import cached_property

from rest_framework import relations, serializers
from rest_framework.utils.field_mapping import get_field_kwargs

from apps.generics.fields.options import (
    ChoicesOptionsSerializer,
    PaginatedOptionsSerializer,
)

# Kwargs accepted by the options fields: base ``Field`` kwargs plus the ones of
# ``ChoicesOptionsSerializer`` and ``PaginatedOptionsBaseSerializer``. Anything else
# coming from the model mapping or the source ``extra_kwargs`` (``allow_blank``,
# ``max_length``, ``allow_empty``...) is dropped, as it only applies to writes.
OPTIONS_FIELD_KWARGS = frozenset(
    {
        'read_only',
        'write_only',
        'required',
        'default',
        'initial',
        'source',
        'label',
        'help_text',
        'style',
        'error_messages',
        'validators',
        'allow_null',
        'choices',
        'queryset',
        'value_field_name',
        'label_field_name',
        'option_serializer_class',
        'filter_field_name',
        'filter_lookup_expr',
    }
)

# Source declared fields that can still be represented as options. Anything else
# declared on the source (nested serializers, method fields, plain fields) is
# excluded, because the write endpoint does not accept a choice/PK for it.
OPTIONS_DECLARED_FIELD_TYPES = (
    serializers.ChoiceField,
    relations.RelatedField,
    relations.ManyRelatedField,
)


class OptionsSerializer(serializers.Serializer):
    """
    Base for options serializers.

    Query params named after fields select which fields are returned
    (``?team&member``); unknown params are ignored.
    """

    @cached_property
    def fields(self):
        fields = super().fields
        params = {}
        if (request := self.context.get('request')) is not None:
            params = getattr(request, 'query_params', None)
            # Plain Django requests (e.g. RequestFactory) have no query_params.
            if params is None:
                params = getattr(request, 'GET', None) or {}
        field_filters = set(params) & set(fields)
        if field_filters:
            return {k: v for k, v in fields.items() if k in field_filters}
        return fields


class OptionsModelSerializer(OptionsSerializer, serializers.ModelSerializer):
    """
    Options serializer built from a source ``ModelSerializer``.

    Model fields with ``choices`` become ``ChoicesOptionsSerializer`` and relations
    become ``serializer_related_field`` (paginated). Read-only fields are skipped.
    Subclasses change ``serializer_related_field`` to scope relation querysets.
    """

    serializer_choice_field = ChoicesOptionsSerializer
    serializer_related_field = PaginatedOptionsSerializer

    def get_source_declared_fields(self) -> dict[str, serializers.Field]:
        serializer_class = getattr(self.Meta, 'serializer_class', None)
        return getattr(serializer_class, '_declared_fields', {})

    @classmethod
    def is_source_declared_field_allowed(cls, field: serializers.Field) -> bool:
        """Whether a field declared on the source can be exposed as options."""
        return isinstance(field, OPTIONS_DECLARED_FIELD_TYPES) and not field.read_only

    def get_extra_kwargs(self):
        """
        Merge the source ``Meta.options_extra_kwargs`` (options-only kwargs such as
        ``label_field_name``/``filter_field_name``, which the write fields do not
        accept) and carry over what the source declared fields restrict: their
        choices and their queryset (organization/active scoping still applies on
        top).
        """
        extra_kwargs = super().get_extra_kwargs()
        options_extra_kwargs = getattr(self.Meta, 'options_extra_kwargs', {})
        for field_name, kwargs in copy.deepcopy(options_extra_kwargs).items():
            extra_kwargs.setdefault(field_name, {}).update(kwargs)
        for field_name, field in self.get_source_declared_fields().items():
            if not self.is_source_declared_field_allowed(field):
                continue
            kwargs = extra_kwargs.get(field_name, {}).copy()
            if isinstance(field, serializers.ChoiceField):
                kwargs['choices'] = list(field.choices.items())
            else:
                related = getattr(field, 'child_relation', field)
                if (queryset := getattr(related, 'queryset', None)) is not None:
                    kwargs['queryset'] = queryset
            extra_kwargs[field_name] = kwargs
        # Write-only fields on the source must still be rendered as options.
        for kwargs in extra_kwargs.values():
            kwargs.pop('write_only', None)
        return extra_kwargs

    def include_extra_kwargs(self, kwargs, extra_kwargs):
        """
        Adapt the DRF field kwargs to the options fields.

        - ``to_field`` (FK to a non-PK field) becomes ``value_field_name``, so the
          option value is what the write endpoint expects.
        - ``many`` is dropped: a to-many relation renders the same single
          paginated envelope as a FK.
        - Unsupported kwargs are dropped (see ``OPTIONS_FIELD_KWARGS``).
        - Every field is optional, since ``?<field>`` may leave it out.
        """
        kwargs = super().include_extra_kwargs(kwargs, extra_kwargs)
        # Any field can be left out with ``?<field>`` selection.
        kwargs['required'] = False
        kwargs.pop('default', None)
        if (to_field := kwargs.pop('to_field', None)) and not kwargs.get(
            'value_field_name'
        ):
            kwargs['value_field_name'] = to_field
        return {k: v for k, v in kwargs.items() if k in OPTIONS_FIELD_KWARGS}

    def get_field_names(self, declared_fields, info):
        """
        Keep only fields the write endpoint accepts as a choice or a PK: model
        fields with ``choices`` and relations, minus read-only fields and source
        declared fields that are not choice/related fields.
        """
        field_name_list = super().get_field_names(declared_fields, info)
        source_declared_fields = self.get_source_declared_fields()
        fields = []
        for field_name in field_name_list:
            source_field = source_declared_fields.get(field_name)
            if source_field is not None and not self.is_source_declared_field_allowed(
                source_field
            ):
                continue
            if field_name in info.fields_and_pk:
                model_field = info.fields_and_pk[field_name]
                field_kwargs = get_field_kwargs(field_name, model_field)
                if 'choices' in field_kwargs:
                    fields.append(field_name)
            elif field_name in info.relations:
                fields.append(field_name)

        extra_kwargs = self.get_extra_kwargs()
        return [
            field_name
            for field_name in fields
            if not extra_kwargs.get(field_name, {}).get('read_only', False)
        ]
