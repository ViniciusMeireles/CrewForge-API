"""
Fields used by form-options serializers.

Two shapes are produced:

- ``ChoicesOptionsSerializer``: fields with fixed ``choices`` render as a plain
  ``[{value, label}]`` array.
- ``PaginatedOptionsSerializer``: relation fields render as a paginated envelope
  ``{count, num_pages, page_number, results: [{value, label}]}`` built from the
  field queryset.

Both act as *fields* inside an options serializer: they ignore the instance being
serialized and render the available options instead.
"""

import logging
from types import SimpleNamespace
from typing import Any

from django.core.paginator import InvalidPage
from django.db import models
from django.db.models import enums, query
from django.db.models.expressions import Combinable, F
from django_filters.conf import settings as filters_settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.settings import api_settings

from apps.generics.fields.fields import get_python_type
from apps.generics.types import OptionType, PageDataType

log = logging.getLogger(__name__)


class OptionBaseSerializer[T](serializers.Serializer):
    """
    Serialize a single ``{value, label}`` option.

    Accepts dicts (e.g. rows from ``QuerySet.values()``) or model instances. The
    keys/attributes read are ``DEFAULT_OPTION_VALUE_FIELD`` and
    ``DEFAULT_OPTION_LABEL_FIELD``; for model instances without those annotations,
    ``pk`` and ``str(obj)`` are used. ``output_type`` casts the value so the OpenAPI
    schema and the JSON type match (e.g. ``int`` for PKs).
    """

    DEFAULT_OPTION_VALUE_FIELD = '_option_value'
    DEFAULT_OPTION_LABEL_FIELD = '_option_label'
    output_type: type = None

    value = serializers.SerializerMethodField(method_name='get_value_option')
    label = serializers.SerializerMethodField(method_name='get_label_option')

    def __init__(
        self,
        option_value_field: str | None = None,
        option_label_field: str | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._option_value_field = option_value_field or self.DEFAULT_OPTION_VALUE_FIELD
        self._option_label_field = option_label_field or self.DEFAULT_OPTION_LABEL_FIELD

    def get_value_option(self, obj) -> T:
        if isinstance(obj, dict):
            value = obj.get(self._option_value_field)
        else:
            value = getattr(obj, self._option_value_field, None)
            if value is None:
                if isinstance(obj, models.Model):
                    value = obj.pk
        if value is None:
            return None

        if self.output_type is None:
            log.warning(f'Output type is None for {self.__class__.__name__}')
            return value

        # Union types such as ``dict | list`` (JSONField) are not callable.
        if not isinstance(self.output_type, type) or type(value) is self.output_type:
            return value

        return self.output_type(value)

    def get_label_option(self, obj) -> str:
        if isinstance(obj, dict):
            label = obj.get(self._option_label_field)
        else:
            label = getattr(obj, self._option_label_field, None)
            if label is None:
                if isinstance(obj, models.Model):
                    label = str(obj)
        return str(label) if label is not None else ''


# Dynamic classes are cached so each (type, base) pair yields a single class.
# Without it, every field instance creates a new class with the same name and
# drf-spectacular reports duplicated components.
_option_serializer_classes: dict[tuple, type[OptionBaseSerializer]] = {}
_paginated_options_serializer_classes: dict[
    tuple, type[PaginatedOptionsBaseSerializer]
] = {}


def _get_type_name(output_type: type) -> str:
    return getattr(output_type, '__name__', 'Any').title()


def _create_option_serializer_class(
    output_type: type,
    base_class: type[OptionBaseSerializer] | None = None,
    namespace: dict[str, Any] | None = None,
    name_prefix: str = 'Option',
) -> type[OptionBaseSerializer]:
    """Return the cached option serializer class typed with ``output_type``."""
    key = (
        output_type,
        base_class,
        name_prefix,
        tuple(sorted((namespace or {}).items())),
    )
    if key not in _option_serializer_classes:
        _option_serializer_classes[key] = _build_option_serializer_class(
            output_type=output_type,
            base_class=base_class,
            namespace=dict(namespace or {}),
            name_prefix=name_prefix,
        )
    return _option_serializer_classes[key]


def _build_option_serializer_class(
    output_type: type,
    base_class: type[OptionBaseSerializer] | None,
    namespace: dict[str, Any],
    name_prefix: str,
) -> type[OptionBaseSerializer]:
    if base_class is None:
        base_class = OptionBaseSerializer[output_type]

    # Re-declared only to attach the concrete value type to the OpenAPI schema.
    @extend_schema_field(output_type)
    def get_value_option(self, obj):
        return base_class.get_value_option(self, obj=obj)

    namespace.setdefault('output_type', output_type)
    namespace.setdefault('get_value_option', get_value_option)
    namespace.setdefault('__doc__', 'Value/label option.')
    return type(  # type: ignore
        f'{name_prefix}{_get_type_name(output_type)}Serializer',
        (base_class,),
        namespace,
    )


class PaginatedOptionsBaseSerializer[T](serializers.Serializer):
    """
    Paginated list of options for a relation field.

    Built by ``ModelSerializer.build_relational_field`` (it receives the related
    ``queryset``), so it must accept the same kwargs as a ``RelatedField``.
    Pagination follows ``DEFAULT_PAGINATION_CLASS`` and reads ``page``/``page_size``
    from the request, which means every relation field in the response shares
    the same page parameters.

    Opt-in kwargs (usually via the source serializer ``Meta.extra_kwargs``):

    - ``label_field_name``: field name or expression annotated as the label;
      defaults to ``str(obj)``.
    - ``value_field_name``: field name or expression for the value; defaults to
      ``pk``.
    - ``filter_field_name`` / ``filter_lookup_expr``: enables text search with
      ``?<field>=<text>``.
    """

    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    option_serializer_class: type[OptionBaseSerializer[T]] | None = None
    output_type: type = None

    count = serializers.SerializerMethodField()
    num_pages = serializers.SerializerMethodField()
    page_number = serializers.SerializerMethodField()
    results = serializers.SerializerMethodField()

    def __init__(
        self,
        queryset: query.QuerySet[models.Model] | None = None,
        value_field_name: Combinable | str | None = None,
        label_field_name: Combinable | str | None = None,
        option_serializer_class: type[OptionBaseSerializer] | None = None,
        filter_field_name: str | None = None,
        filter_lookup_expr: str | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.queryset = queryset
        self.value_field_name = value_field_name
        self.label_field_name = label_field_name
        self.option_serializer_class = option_serializer_class
        self.filter_field_name = filter_field_name
        if filter_lookup_expr is None:
            filter_lookup_expr = filters_settings.DEFAULT_LOOKUP_EXPR
        self.filter_lookup_expr = filter_lookup_expr
        self._paginator = None
        self._page_data: PageDataType | None = None

    def get_option_serializer_class(self) -> type[OptionBaseSerializer]:
        if self.option_serializer_class is not None:
            return self.option_serializer_class
        return _create_option_serializer_class(output_type=self.output_type)

    def get_queryset(self) -> query.QuerySet[models.Model]:
        """
        Base queryset of the options. Scoping mixins (organization, active)
        override this method and filter on top of it.
        """
        queryset = self.queryset.all()
        # Pagination over an unordered queryset is unstable between pages.
        if not queryset.ordered:
            queryset = queryset.order_by('pk')
        return queryset

    def filter_queryset(
        self, queryset: query.QuerySet[models.Model]
    ) -> query.QuerySet[models.Model]:
        """
        Apply ``?<field>=<text>`` as a search filter, only when the field opted in
        with ``filter_field_name`` or ``label_field_name``. Otherwise the query
        param just selects the field (see ``OptionsSerializer.fields``).
        """
        if (
            not self.filter_field_name and not self.label_field_name
        ) or not self.source_attrs:
            log.debug(
                'Filter field and label field are not set in %s.%s',
                self.parent.__class__.__name__ if self.parent else None,
                self.field_name,
            )
            return queryset

        request = self.context.get('request')
        params = getattr(request, 'query_params', None) or {}
        if filter_value := params.get(self.source_attrs[0]):
            # Without ``filter_field_name``, search on the annotated label.
            option_serializer_class = self.get_option_serializer_class()
            field_name = (
                self.filter_field_name
                or option_serializer_class.DEFAULT_OPTION_LABEL_FIELD
            )
            field_expr = '%s__%s' % (field_name, self.filter_lookup_expr)
            queryset = queryset.filter(**{field_expr: filter_value})
        return queryset

    def get_object_list(
        self,
    ) -> (
        query.QuerySet[models.Model, models.Model]
        | query.QuerySet[models.Model, dict[str, Any]]
    ):
        """
        Return the queryset to paginate. A configured value is annotated on the
        rows; with a configured label, rows are returned as ``values()`` dicts.
        Otherwise model instances are returned and rendered with ``pk``/``str(obj)``.
        """
        option_serializer_class = self.get_option_serializer_class()
        value_key = option_serializer_class.DEFAULT_OPTION_VALUE_FIELD
        label_key = option_serializer_class.DEFAULT_OPTION_LABEL_FIELD
        value_expression = self._get_expression(self.value_field_name)
        label_expression = self._get_expression(self.label_field_name)
        annotations = {}
        if value_expression is not None:
            annotations[value_key] = value_expression
        if label_expression is not None:
            annotations[label_key] = label_expression
            annotations.setdefault(value_key, F('pk'))

        queryset = self.get_queryset()
        if annotations:
            queryset = queryset.annotate(**annotations)

        queryset = self.filter_queryset(queryset=queryset)

        if label_expression is not None:
            return queryset.values(*annotations)
        return queryset

    @staticmethod
    def _get_expression(field_name: Combinable | str | None) -> Combinable | None:
        if not field_name:
            return None
        return F(field_name) if isinstance(field_name, str) else field_name

    def _get_page_data(self) -> PageDataType | None:
        request = self.context.get('request')
        paginator = self.pagination_class()

        if not (page_size := paginator.get_page_size(request)):
            return None

        django_paginator = paginator.django_paginator_class(
            self.get_object_list(),
            page_size,
        )
        page_number = paginator.get_page_number(request, django_paginator)

        try:
            page = django_paginator.page(page_number)
        except InvalidPage as exc:
            msg = paginator.invalid_page_message.format(
                page_number=page_number, message=str(exc)
            )
            raise NotFound(msg) from exc

        self._page_data = PageDataType(
            count=page.paginator.count,
            num_pages=django_paginator.num_pages,
            page_number=int(page_number or 0),
            data=page.object_list,
        )
        return self._page_data

    def get_page_data(self, cache: bool = True) -> PageDataType | None:
        """Page data computed once and shared by the four envelope fields."""
        if self._page_data is None or not cache:
            self._page_data = self._get_page_data()
        return self._page_data

    def get_count(self, instance) -> int:
        if (page_data := self.get_page_data()) is None:
            return 0
        return page_data.get('count')

    def get_num_pages(self, instance) -> int:
        if (page_data := self.get_page_data()) is None:
            return 0
        return page_data.get('num_pages')

    def get_page_number(self, instance) -> int:
        if (page_data := self.get_page_data()) is None:
            return 0
        return page_data.get('page_number')

    def get_results(self, instance) -> list[dict[str, Any]]:
        if (page_data := self.get_page_data()) is None:
            return []
        serializer_class = self.get_option_serializer_class()
        return serializer_class(  # type: ignore
            instance=page_data.get('data'),
            many=True,
            context=self.context,
        ).data

    def get_attribute(self, instance):
        # The options do not depend on the instance being serialized; return a
        # non-None placeholder so DRF still calls ``to_representation``.
        return SimpleNamespace(pk=None)


def _create_paginated_options_serializer_class(
    output_type: type,
    bases: tuple[type] | None = None,
) -> type[PaginatedOptionsBaseSerializer]:
    """Return the cached paginated serializer class typed with ``output_type``."""
    key = (output_type, bases or ())
    if key not in _paginated_options_serializer_classes:
        _paginated_options_serializer_classes[key] = (
            _build_paginated_options_serializer_class(
                output_type=output_type,
                bases=bases,
            )
        )
    return _paginated_options_serializer_classes[key]


def _build_paginated_options_serializer_class(
    output_type: type,
    bases: tuple[type] | None = None,
    namespace: dict[str, Any] | None = None,
) -> type[PaginatedOptionsBaseSerializer]:
    bases = bases or ()
    namespace = namespace or {}
    has_base_paginated = bool(
        [x for x in bases if issubclass(x, PaginatedOptionsBaseSerializer)]
    )
    if not has_base_paginated:
        bases += (PaginatedOptionsBaseSerializer[output_type],)

    base_class = type(
        f'Paginated{_get_type_name(output_type)}BaseOptionsSerializer',
        bases,
        namespace,
    )

    option_serializer_class = _create_option_serializer_class(output_type=output_type)

    # Re-declared only to type ``results`` items in the OpenAPI schema.
    @extend_schema_field(option_serializer_class)
    def get_results(self, instance):
        return base_class.get_results(self=self, instance=instance)

    namespace = namespace or {}
    namespace.setdefault('output_type', output_type)
    namespace.setdefault('get_results', get_results)
    namespace.setdefault('__doc__', 'Paginated value/label options.')
    return type(  # type: ignore
        f'Paginated{_get_type_name(output_type)}OptionsSerializer',
        (base_class,),
        namespace,
    )


class PaginatedOptionsSerializer(PaginatedOptionsBaseSerializer):
    """
    Entry point used as ``serializer_related_field``.

    On instantiation it infers the value type (from ``option_serializer_class``
    or from the queryset ``value_field_name``/``pk`` output field) and returns an
    instance of a typed subclass, e.g. ``PaginatedIntOptionsSerializer``. Scoping
    mixins placed before this class in the MRO are kept in the typed subclass.
    """

    @classmethod
    def output_init(
        cls,
        output_type: type,
        *args,
        **kwargs,
    ) -> PaginatedOptionsBaseSerializer:
        serializer_class = _create_paginated_options_serializer_class(
            output_type,
            bases=(cls,),
        )
        return serializer_class(*args, **kwargs)

    def __new__(cls, *args, **kwargs):
        # Already a typed subclass: regular instantiation.
        if cls.output_type:
            return super().__new__(cls, *args, **kwargs)

        output_type: type | None = kwargs.pop('output_type', None)
        if output_type is None:
            option_serializer_class = kwargs.get(
                'option_serializer_class',
                getattr(cls, 'option_serializer_class', None),
            )
            output_type = getattr(option_serializer_class, 'output_type', None)
            if not output_type and (queryset := kwargs.get('queryset')) is not None:
                # Resolve the value expression to read its Django output field.
                value_field_name = kwargs.get('value_field_name') or 'pk'
                if isinstance(value_field_name, str):
                    value_expression = F(value_field_name)
                else:
                    value_expression = value_field_name
                expression = value_expression.resolve_expression(
                    query=queryset.all().query,
                )
                output_field = expression.output_field
                output_type = get_python_type(output_field)
        if output_type is None:
            raise TypeError('output_type must be provided')
        return cls.output_init(*args, output_type=output_type, **kwargs)


class ChoicesOptionsSerializer(OptionBaseSerializer):
    """
    Entry point used as ``serializer_choice_field``.

    Called with ``choices=...`` (as ``ModelSerializer.build_standard_field`` does),
    it returns a list serializer over the ``{value, label}`` pairs, typed after the
    first choice value. The child is instantiated again with ``output_type`` only,
    which returns the typed option class.
    """

    DEFAULT_OPTION_VALUE_FIELD = 'value'
    DEFAULT_OPTION_LABEL_FIELD = 'label'

    def __new__(cls, *args, **kwargs):
        if choices := kwargs.pop('choices', None):
            list_kwargs = kwargs.copy()
            if isinstance(choices, enums.ChoicesType):
                choices = choices.choices
            data = [OptionType(value=value, label=label) for value, label in choices]
            output_type = type(data[0].get('value')) if data else None
            list_kwargs.update(
                {
                    'data': data,
                    'output_type': output_type,
                }
            )

            # The list renders its own ``initial_data`` (the choices) instead of
            # reading an attribute from the serialized instance.
            meta = getattr(cls, 'Meta', None)
            if not getattr(meta, 'list_serializer_class', None):

                class ListOptionsSerializer(serializers.ListSerializer):
                    def get_attribute(self, instance):
                        return self.initial_data

                if meta is None:
                    cls.Meta = type(
                        'Meta', (), {'list_serializer_class': ListOptionsSerializer}
                    )
                else:
                    meta.list_serializer_class = ListOptionsSerializer

            return cls.many_init(*args, **list_kwargs)
        if output_type := kwargs.pop('output_type', None):
            klass = _create_option_serializer_class(
                output_type=output_type,
                namespace={
                    'DEFAULT_OPTION_VALUE_FIELD': cls.DEFAULT_OPTION_VALUE_FIELD,
                    'DEFAULT_OPTION_LABEL_FIELD': cls.DEFAULT_OPTION_LABEL_FIELD,
                },
                name_prefix='ChoiceOption',
            )
            return klass(*args, **kwargs)
        return super().__new__(cls, *args, **kwargs)
