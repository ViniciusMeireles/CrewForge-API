"""
Serializers that describe the selectable fields of a write serializer or of a
list filterset.

An options serializer is generated per ViewSet action (see
``OptionsBaseModelMixin``). For ``create``/``update`` ``Meta.serializer_class``
points to the source write serializer, and only fields the write endpoint accepts
as a choice or a PK are exposed. For ``list`` ``Meta.filterset_class`` points to
the source filterset, and only filters that take a choice or a PK are exposed.
"""

import copy
from functools import cached_property

from django.core.exceptions import ImproperlyConfigured
from django_filters import filters, filterset
from django_filters.utils import get_model_field
from rest_framework import relations, serializers
from rest_framework.utils import model_meta
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
        'choices_filter',
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

    ``Meta.options_extra_kwargs`` of the source is validated when the fields are
    built (at class creation, through the ViewSet metaclass): a key that is not a
    field of the source, or a kwarg that is neither in ``options_field_kwargs`` nor
    in ``options_meta_kwargs`` (read by the serializer, not passed to the field),
    raises ``ImproperlyConfigured`` instead of being ignored.
    """

    options_field_kwargs = OPTIONS_FIELD_KWARGS
    options_meta_kwargs: frozenset[str] = frozenset()

    def get_options_extra_kwargs(self) -> dict[str, dict]:
        return {}

    def get_options_source_field_names(self) -> set[str]:
        raise NotImplementedError

    def check_options_extra_kwargs(self) -> None:
        options_extra_kwargs = self.get_options_extra_kwargs()
        label = self.__class__.__name__
        field_names = self.get_options_source_field_names()
        if unknown_fields := set(options_extra_kwargs) - field_names:
            raise ImproperlyConfigured(
                f'{label}: Meta.options_extra_kwargs declares unknown fields '
                f'{sorted(unknown_fields)}.'
            )
        allowed = self.options_field_kwargs | self.options_meta_kwargs
        for field_name, kwargs in options_extra_kwargs.items():
            if unknown := set(kwargs) - allowed:
                raise ImproperlyConfigured(
                    f'{label}.{field_name}: unknown options kwargs {sorted(unknown)} '
                    f'in Meta.options_extra_kwargs (allowed: {sorted(allowed)}).'
                )

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

    def get_options_extra_kwargs(self) -> dict[str, dict]:
        return getattr(self.Meta, 'options_extra_kwargs', {})

    def get_options_source_field_names(self) -> set[str]:
        info = model_meta.get_field_info(self.Meta.model)
        return (
            set(info.fields_and_pk)
            | set(info.relations)
            | set(self.get_source_declared_fields())
        )

    def get_fields(self):
        self.check_options_extra_kwargs()
        return super().get_fields()

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
        options_extra_kwargs = self.get_options_extra_kwargs()
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
        - Unsupported kwargs are dropped (see ``options_field_kwargs``).
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
        return {k: v for k, v in kwargs.items() if k in self.options_field_kwargs}

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


OPTIONS_FILTER_LOOKUPS = frozenset({'exact', 'in'})


class OptionsFilterSetSerializer(OptionsSerializer):
    """
    Options serializer built from a source ``FilterSet``.

    One field per filter, keyed by the filter name (the list query param):

    - filters with ``choices`` (``ChoiceFilter``, ``OrderingFilter``...) and
      ``exact``/``in`` filters on a model field with ``choices`` become
      ``ChoicesOptionsSerializer``;
    - filters with a ``queryset`` (``ModelChoiceFilter``,
      ``ModelMultipleChoiceFilter``) become ``serializer_related_field``
      (paginated).

    Any other filter (text, number, boolean) is skipped, and so are filters with
    ``method=`` unless they declare their own ``choices``/``queryset``. The filter
    ``label``/``help_text`` are kept. Per-filter kwargs come from the source
    ``Meta.options_extra_kwargs``.
    """

    serializer_choice_field = ChoicesOptionsSerializer
    serializer_related_field = PaginatedOptionsSerializer

    def get_filterset_class(self) -> type[filterset.BaseFilterSet]:
        return self.Meta.filterset_class

    def get_options_extra_kwargs(self) -> dict[str, dict]:
        filterset_meta = getattr(self.get_filterset_class(), 'Meta', None)
        return getattr(filterset_meta, 'options_extra_kwargs', {})

    def get_options_source_field_names(self) -> set[str]:
        return set(self.get_filterset_class().base_filters)

    def get_extra_kwargs(self) -> dict[str, dict]:
        return copy.deepcopy(self.get_options_extra_kwargs())

    def get_fields(self):
        self.check_options_extra_kwargs()
        filterset_class = self.get_filterset_class()
        model = filterset_class._meta.model
        extra_kwargs = self.get_extra_kwargs()
        fields = {}
        for filter_name, filter_ in filterset_class.base_filters.items():
            field_info = self.build_filter_field(filter_, model)
            if field_info is None:
                continue
            field_class, kwargs = field_info
            if filter_.label is not None:
                kwargs['label'] = filter_.label
            if (help_text := filter_.extra.get('help_text')) is not None:
                kwargs['help_text'] = help_text
            kwargs.update(extra_kwargs.get(filter_name, {}))
            kwargs['required'] = False
            kwargs = {k: v for k, v in kwargs.items() if k in self.options_field_kwargs}
            fields[filter_name] = field_class(**kwargs)
        return fields

    def build_filter_field(
        self, filter_: filters.Filter, model
    ) -> tuple[type[serializers.Field], dict] | None:
        """Return the options field class and kwargs of a filter, or ``None``."""
        if choices := self.get_filter_choices(filter_, model):
            return self.serializer_choice_field, {'choices': choices}
        if isinstance(filter_, filters.QuerySetRequestMixin):
            queryset = filter_.get_queryset(self.context.get('request'))
            if queryset is None:
                return None
            kwargs = {'queryset': queryset}
            if to_field_name := filter_.extra.get('to_field_name'):
                kwargs['value_field_name'] = to_field_name
            return self.serializer_related_field, kwargs
        return None

    @staticmethod
    def get_filter_choices(filter_: filters.Filter, model) -> list | None:
        choices = filter_.extra.get('choices')
        if callable(choices):
            choices = choices()
        if choices:
            return list(choices)
        if filter_.method is not None:
            return None
        if model is None or filter_.lookup_expr not in OPTIONS_FILTER_LOOKUPS:
            return None
        if isinstance(filter_, filters.QuerySetRequestMixin):
            return None
        model_field = get_model_field(model, filter_.field_name)
        if model_field is None or model_field.is_relation:
            return None
        if choices := getattr(model_field, 'choices', None):
            return list(choices)
        return None
