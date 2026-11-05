from django.test import SimpleTestCase
from django.utils import translation
from django_filters.rest_framework import filters, filterset
from rest_framework import serializers

from apps.generics.mixins.serializers import ModelSerializerFieldsMixin
from apps.generics.utils.filters import orderable_filter_factory


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


class OrderableFilterFactoryTestCase(SimpleTestCase):
    def test_adds_ordering_filter(self):
        filterset_class = orderable_filter_factory(_SimpleSer, _BaseFilterSet)
        self.assertIn('order_by', filterset_class.declared_filters)

    def test_ordering_filter_choices_are_static_with_lazy_labels(self):
        filterset_class = orderable_filter_factory(_SerWithMixin, _BaseFilterSet)
        order_by = filterset_class.declared_filters['order_by']
        choices = order_by.extra['choices']
        self.assertIsInstance(choices, list)
        with translation.override('en'):
            self.assertEqual(
                [(value, str(label)) for value, label in choices],
                [('name', 'Name'), ('-name', 'Descending Name')],
            )
        with translation.override('pt-br'):
            self.assertEqual(
                [(value, str(label)) for value, label in choices],
                [('name', 'Nome'), ('-name', 'Nome (decrescente)')],
            )

    def test_respects_existing_order_by(self):
        self.assertIs(
            orderable_filter_factory(_SimpleSer, _OrderedFilterSet), _OrderedFilterSet
        )

    def test_wraps_serializer_with_mixin_if_missing(self):
        filterset_class = orderable_filter_factory(_SimpleSer, _BaseFilterSet)
        self.assertIsNotNone(filterset_class.declared_filters['order_by'])

    def test_does_not_wrap_if_mixin_present(self):
        filterset_class = orderable_filter_factory(_SerWithMixin, _BaseFilterSet)
        order_by = filterset_class.declared_filters['order_by']
        self.assertIsInstance(order_by, filters.OrderingFilter)
