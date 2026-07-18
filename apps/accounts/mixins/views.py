from django.db.models.expressions import Combinable, F
from django_filters.rest_framework import filters, filterset
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.mixins.requests import OrganizationScopedRequestMixin
from apps.generics.mixins.serializers import ModelSerializerFieldsMixin
from apps.generics.serializers.choices import ChoiceSerializer


class ModelViewSetMetaclass(type):
    def __new__(cls, name, bases, attrs):
        klass = super().__new__(cls, name, bases, attrs)
        if not attrs.get('auto_orderable_filter', False):
            return klass
        http_method_names = attrs.get('http_method_names', [])
        if http_method_names and 'get' not in http_method_names:
            return klass
        if not cls._get_filterset_class(klass=klass):
            return klass
        klass.filterset_class = cls._orderable_filter_factory(klass=klass)
        return klass

    @classmethod
    def _get_filterset_class(cls, klass) -> type[filterset.FilterSet] | None:
        view_obj = klass()
        filterset_class = getattr(view_obj, 'filterset_class', None)
        if not filterset_class or not issubclass(filterset_class, filterset.FilterSet):
            return None
        return filterset_class

    @classmethod
    def _get_list_serializer_class(cls, klass: type) -> type[serializers.Serializer]:
        view_obj = klass()
        view_obj.action = 'list'
        return view_obj.get_serializer_class()

    @classmethod
    def _orderable_filter_factory(cls, klass: type) -> type[filterset.FilterSet]:
        filterset_class: type[filterset.FilterSet] = cls._get_filterset_class(  # type: ignore
            klass=klass
        )
        if 'order_by' in filterset_class.declared_filters:
            return filterset_class

        serializer_class = cls._get_list_serializer_class(klass=klass)
        if not issubclass(serializer_class, ModelSerializerFieldsMixin):
            serializer_class = type(
                f'Orderable{serializer_class.__name__}',
                (ModelSerializerFieldsMixin, serializer_class),
                {},
            )

        return type(  # type: ignore
            f'Orderable{filterset_class.__name__}',
            (filterset_class,),
            {
                'order_by': filters.OrderingFilter(
                    choices=serializer_class.orderable_fields_choices
                ),
            },
        )


class ModelViewSetMixin(
    OrganizationScopedRequestMixin,
    metaclass=ModelViewSetMetaclass,
):
    """Mixin for views to add user, member, and organization properties."""

    def perform_destroy(self, instance):
        if hasattr(instance, 'is_active'):
            instance.inactivate()
        else:
            super().perform_destroy(instance)

    def get_label_expression(self) -> str | Combinable:
        """
        Returns the label expression for the queryset. This is used for choices options.
        """
        if label_expression := getattr(self, 'label_expression', None):
            return label_expression
        raise NotImplementedError('Subclasses must implement this method.')

    def get_value_expression(self) -> str | Combinable:
        """
        Returns the value expression for the queryset. This is used for choices options.
        """
        if value_expression := getattr(self, 'value_expression', None):
            return value_expression
        elif self.lookup_field:
            return self.lookup_field
        return 'pk'

    @action(detail=False, methods=['get'], url_path='choices')
    def choices(self, request, *args, **kwargs):
        """List teams for choices (value/label format)."""
        queryset = self.filter_queryset(self.get_queryset())

        label = self.get_label_expression()
        value = self.get_value_expression()
        choices_queryset = queryset.annotate(
            _choice_label=F(label) if isinstance(label, str) else label,
            _choice_value=F(value) if isinstance(value, str) else value,
        ).values('_choice_value', '_choice_label')

        choices_page = self.paginate_queryset(choices_queryset)
        if choices_page is not None:
            serializer = ChoiceSerializer(choices_page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ChoiceSerializer(choices_queryset, many=True)
        return Response(serializer.data)


class OrganizationScopedViewSetMixin(OrganizationScopedRequestMixin):
    organization_filter = 'organization_id'
    base_filters = {}

    def get_base_queryset_filters(self) -> dict:
        return dict(self.base_filters)

    def get_organization_filter_kwargs(self) -> dict:
        return {self.organization_filter: self.auth_organization_id}

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                **self.get_organization_filter_kwargs(),
                **self.get_base_queryset_filters(),
            )
        )
