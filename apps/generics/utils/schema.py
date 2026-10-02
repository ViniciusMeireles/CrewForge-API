from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import serializers

from apps.generics.fields.options import PaginatedOptionsBaseSerializer
from apps.generics.models.abstracts import BaseModel
from apps.generics.utils.models import get_verbose_name, get_verbose_name_plural


def extend_schema_retrieve(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = format_lazy(_('Retrieve a specific {name}.'), name=get_verbose_name(model))
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_list(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = format_lazy(_('List all {name}.'), name=get_verbose_name_plural(model))
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_create(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = format_lazy(_('Create a new {name}.'), name=get_verbose_name(model))
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_destroy(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = format_lazy(_('Delete a {name}.'), name=get_verbose_name(model))
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_update(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = format_lazy(_('Update a {name}.'), name=get_verbose_name(model))
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_partial_update(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = format_lazy(_('Partially update a {name}.'), name=get_verbose_name(model))
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_options_create(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = format_lazy(_('Create options for a {name}.'), name=get_verbose_name(model))
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_options_update(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = format_lazy(_('Update options for a {name}.'), name=get_verbose_name(model))
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def _get_form_options_field_description(
    field_name: str, field: serializers.Field, search: bool = True
) -> str:
    if not search:
        return format_lazy(
            _(
                'Return only `{field}`. Search is disabled on this route: the value '
                'is ignored.'
            ),
            field=field_name,
        )
    if not isinstance(field, PaginatedOptionsBaseSerializer):
        return format_lazy(
            _(
                'Return only `{field}`. A non-empty value is a regular expression '
                'matched against the label or the value of each option, ignoring '
                'case and accents.'
            ),
            field=field_name,
        )
    if field.filter_field_name or field.label_field_name:
        return format_lazy(
            _(
                'Return only `{field}` (paginated). A non-empty value filters its '
                'options by label (`{lookup}`).'
            ),
            field=field_name,
            lookup=field.filter_lookup_expr,
        )
    return format_lazy(
        _(
            'Return only `{field}` (paginated). Search is not enabled for this '
            'field: the value is ignored.'
        ),
        field=field_name,
    )


def _get_form_options_pagination_parameters(
    field: PaginatedOptionsBaseSerializer,
) -> list[OpenApiParameter]:
    paginator = field.get_pagination_class()()
    scope = _(
        'Applies to every paginated field in the response; combine with '
        '`?<field>` to paginate a single one.'
    )
    page_size_description = paginator.page_size_query_description
    if paginator.max_page_size:
        page_size_description = format_lazy(
            '{} {}',
            page_size_description,
            format_lazy(_('Maximum: {max}.'), max=paginator.max_page_size),
        )
    return [
        OpenApiParameter(
            name=paginator.page_query_param,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=False,
            description=format_lazy('{} {}', paginator.page_query_description, scope),
        ),
        OpenApiParameter(
            name=paginator.page_size_query_param,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=False,
            description=format_lazy('{} {}', page_size_description, scope),
        ),
    ]


def get_form_options_parameters(
    serializer_class: type[serializers.Serializer],
    search: bool = True,
) -> list[OpenApiParameter]:
    """
    Query parameters of a form-options route.

    One parameter per field, which selects that field in the response (and, on
    paginated fields with a search opt-in, filters its options). ``page`` and
    ``page_size`` are added only when at least one field is paginated. With
    ``search=False`` (``options_search`` on the ViewSet) the value is documented
    as ignored.
    """
    fields = serializer_class({}).get_fields()
    parameters = [
        OpenApiParameter(
            name=field_name,
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=False,
            allow_blank=True,
            description=_get_form_options_field_description(
                field_name, field, search=search
            ),
        )
        for field_name, field in fields.items()
    ]
    paginated_fields = [
        field
        for field in fields.values()
        if isinstance(field, PaginatedOptionsBaseSerializer)
    ]
    if paginated_fields:
        parameters += _get_form_options_pagination_parameters(paginated_fields[0])
    return parameters


def extend_schema_model_view_set(
    *,
    model: type[BaseModel],
    **kwargs,
):
    kwargs.setdefault('retrieve', extend_schema_retrieve(model=model))
    kwargs.setdefault('list', extend_schema_list(model=model))
    kwargs.setdefault('create', extend_schema_create(model=model))
    kwargs.setdefault('destroy', extend_schema_destroy(model=model))
    kwargs.setdefault('update', extend_schema_update(model=model))
    kwargs.setdefault('partial_update', extend_schema_partial_update(model=model))
    return extend_schema_view(**kwargs)
