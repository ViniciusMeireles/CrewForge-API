from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers
from rest_framework import status as http_status

from apps.generics.models.abstracts import BaseModel
from apps.generics.utils.models import get_verbose_name, get_verbose_name_plural


def extend_schema_choices_route(
    *,
    model: type[BaseModel],
    **kwargs,
):
    """
    Extend schema for choices route.
    This function is used to extend the schema for a choices route in the API.
    """
    description = _(
        'List %(name_plural)s for choices (value/label format).'
        % {'name_plural': model._meta.verbose_name_plural.lower()}
    )
    kwargs.setdefault('tags', model.schema_tags())
    kwargs.setdefault('description', description)
    kwargs.setdefault(
        'responses',
        {
            http_status.HTTP_200_OK: OpenApiResponse(
                response=inline_serializer(
                    name=f'{model.__name__}ChoicesResponse',
                    fields={
                        'value': serializers.IntegerField(),
                        'label': serializers.CharField(),
                    },
                    many=True,
                ),
                examples=[
                    OpenApiExample(
                        name=str(_('Example response')),
                        value=[
                            {
                                'value': 1,
                                'label': f'{get_verbose_name(model).capitalize()} 1',
                            },
                            {
                                'value': 2,
                                'label': f'{get_verbose_name(model).capitalize()} 2',
                            },
                        ],
                        response_only=True,
                    )
                ],
                description=description,
            )
        },
    )
    return extend_schema(**kwargs)


def extend_schema_retrieve(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    kwargs.setdefault(
        'description',
        _('Retrieve a specific %(name)s.' % {'name': get_verbose_name(model)}),
    )
    return extend_schema(**kwargs)


def extend_schema_list(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    kwargs.setdefault(
        'description',
        _('List all %(name)s.' % {'name': get_verbose_name_plural(model)}),
    )
    return extend_schema(**kwargs)


def extend_schema_create(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    kwargs.setdefault(
        'description',
        _('Create a new %(name)s.' % {'name': get_verbose_name(model)}),
    )
    return extend_schema(**kwargs)


def extend_schema_destroy(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    kwargs.setdefault(
        'description',
        _('Delete a %(name)s.' % {'name': get_verbose_name(model)}),
    )
    return extend_schema(**kwargs)


def extend_schema_update(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    kwargs.setdefault(
        'description', _('Update a %(name)s.' % {'name': get_verbose_name(model)})
    )
    return extend_schema(**kwargs)


def extend_schema_partial_update(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    kwargs.setdefault(
        'description',
        _('Partially update a %(name)s.' % {'name': get_verbose_name(model)}),
    )
    return extend_schema(**kwargs)


def extend_schema_options(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    kwargs.setdefault(
        'description',
        _('Get %(name)s options.' % {'name': get_verbose_name(model)}),
    )
    return extend_schema(**kwargs)


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
    kwargs.setdefault('options', extend_schema_options(model=model))
    kwargs.setdefault('choices', extend_schema_choices_route(model=model))
    return extend_schema_view(**kwargs)
