from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)

from apps.generics.models.abstracts import BaseModel
from apps.generics.utils.models import get_verbose_name, get_verbose_name_plural


def extend_schema_retrieve(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = _('Retrieve a specific %(name)s.' % {'name': get_verbose_name(model)})
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_list(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = _('List all %(name)s.' % {'name': get_verbose_name_plural(model)})
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_create(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = _('Create a new %(name)s.' % {'name': get_verbose_name(model)})
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_destroy(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = _('Delete a %(name)s.' % {'name': get_verbose_name(model)})
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_update(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = _('Update a %(name)s.' % {'name': get_verbose_name(model)})
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_partial_update(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = _('Partially update a %(name)s.' % {'name': get_verbose_name(model)})
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_options_create(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = _('Create options for a %(name)s.' % {'name': get_verbose_name(model)})
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
    return extend_schema(**kwargs)


def extend_schema_options_update(model: type[BaseModel], **kwargs):
    kwargs.setdefault('tags', model.schema_tags())
    msg = _('Update options for a %(name)s.' % {'name': get_verbose_name(model)})
    kwargs.setdefault('description', msg)
    kwargs.setdefault('summary', msg)
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
    return extend_schema_view(**kwargs)
