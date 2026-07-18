import copy

from django.core.exceptions import FieldDoesNotExist
from django.db.models import ForeignObjectRel
from django.forms.utils import pretty_name
from django.utils.functional import classproperty
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.utils import model_meta


class ModelSerializerFieldsMixin(serializers.ModelSerializer):
    @classproperty
    def all_model_fields(cls) -> list[str]:
        model = getattr(cls.Meta, 'model', None)
        declared_fields = copy.deepcopy(cls._declared_fields)

        model_info = model_meta.get_field_info(model)
        fields = (
            [model_info.pk.name]
            + list(declared_fields)
            + list(model_info.fields)
            + list(model_info.forward_relations)
        )
        if exclude := getattr(cls.Meta, 'exclude', None):
            fields = [f for f in fields if f not in exclude]
        return fields

    @classmethod
    def _get_verbose_name_field(cls, field_name: str) -> str | None:
        verbose_name = str(_(pretty_name(field_name)))
        if not (model_class := getattr(cls.Meta, 'model', None)):
            return verbose_name
        opts = model_class._meta
        field = opts.get_field(field_name)
        if isinstance(field, ForeignObjectRel):
            return None
        if field.verbose_name:
            return capfirst(field.verbose_name)
        return verbose_name

    @classproperty
    def orderable_fields_choices(cls) -> list[tuple[str, str]]:
        fields = getattr(cls.Meta, 'fields', None)
        if fields is None or fields == serializers.ALL_FIELDS:
            fields = cls.all_model_fields

        declared_fields = copy.deepcopy(cls._declared_fields)
        declared_fields_exclude = []
        for field_name, serializer_field in declared_fields.items():
            if (
                isinstance(
                    serializer_field,
                    (serializers.BaseSerializer, serializers.SerializerMethodField),
                )
                or serializer_field.write_only
            ):
                declared_fields_exclude.append(field_name)

        choices = []
        for field in fields:
            if field in declared_fields_exclude:
                continue
            try:
                get_verbose_name = cls._get_verbose_name_field(field)
            except FieldDoesNotExist:
                continue
            if get_verbose_name:
                choices.append((field, get_verbose_name))
        ascending = sorted(choices, key=lambda x: x[1])
        descending_label = _('Descending %(label)s')
        descending = [
            (f'-{field}', descending_label % {'label': label})
            for field, label in ascending
        ]
        return [
            val for pair in zip(ascending, descending, strict=False) for val in pair
        ]
