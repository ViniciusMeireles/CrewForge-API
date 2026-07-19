from django.test import SimpleTestCase
from django_filters.rest_framework import filters, filterset
from rest_framework import serializers

from apps.accounts.mixins.views import ModelViewSetMetaclass
from apps.generics.mixins.serializers import ModelSerializerFieldsMixin


class _BaseFilterSet(filterset.FilterSet):
    name = filters.CharFilter()


class _OrderedFilterSet(_BaseFilterSet):
    order_by = filters.OrderingFilter()


class _SimpleSer(serializers.Serializer):
    class Meta:
        fields = ['name']


class _SerWithMixin(ModelSerializerFieldsMixin, serializers.Serializer):
    class Meta:
        fields = ['name']


class OrderableFilterMetaclassTestCase(SimpleTestCase):
    def test_adds_ordering_filter(self):
        class TV(metaclass=ModelViewSetMetaclass):
            filterset_class = _BaseFilterSet
            http_method_names = ['get']
            auto_orderable_filter = True
            serializer_class = _SimpleSer

            def get_serializer_class(self):
                return self.serializer_class

        self.assertIn('order_by', TV.filterset_class.declared_filters)

    def test_skipped_when_flag_false(self):
        class TV(metaclass=ModelViewSetMetaclass):
            filterset_class = _BaseFilterSet
            http_method_names = ['get']
            serializer_class = _SimpleSer

            def get_serializer_class(self):
                return self.serializer_class

        self.assertIs(TV.filterset_class, _BaseFilterSet)

    def test_skipped_when_no_get_method(self):
        class TV(metaclass=ModelViewSetMetaclass):
            filterset_class = _BaseFilterSet
            http_method_names = ['post', 'put']
            auto_orderable_filter = True
            serializer_class = _SimpleSer

            def get_serializer_class(self):
                return self.serializer_class

        self.assertIs(TV.filterset_class, _BaseFilterSet)

    def test_skipped_when_no_filterset_class(self):
        class TV(metaclass=ModelViewSetMetaclass):
            http_method_names = ['get']
            auto_orderable_filter = True
            serializer_class = _SimpleSer

            def get_serializer_class(self):
                return self.serializer_class

        self.assertFalse(hasattr(TV, 'filterset_class'))

    def test_respects_existing_order_by(self):
        class TV(metaclass=ModelViewSetMetaclass):
            filterset_class = _OrderedFilterSet
            http_method_names = ['get']
            auto_orderable_filter = True
            serializer_class = _SimpleSer

            def get_serializer_class(self):
                return self.serializer_class

        self.assertIs(TV.filterset_class, _OrderedFilterSet)

    def test_wraps_serializer_with_mixin_if_missing(self):
        class TV(metaclass=ModelViewSetMetaclass):
            filterset_class = _BaseFilterSet
            http_method_names = ['get']
            auto_orderable_filter = True
            serializer_class = _SimpleSer

            def get_serializer_class(self):
                return self.serializer_class

        order_by = TV.filterset_class.declared_filters['order_by']
        self.assertIsNotNone(order_by)

    def test_does_not_wrap_if_mixin_present(self):
        class TV(metaclass=ModelViewSetMetaclass):
            filterset_class = _BaseFilterSet
            http_method_names = ['get']
            auto_orderable_filter = True
            serializer_class = _SerWithMixin

            def get_serializer_class(self):
                return self.serializer_class

        order_by = TV.filterset_class.declared_filters['order_by']
        self.assertIsInstance(order_by, filters.OrderingFilter)
