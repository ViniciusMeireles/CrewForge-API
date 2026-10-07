from django_filters import filters, filterset
from rest_framework.serializers import BaseSerializer

from apps.generics.mixins.serializers import ModelSerializerFieldsMixin

TIEBREAKER_FIELDS = frozenset({'pk', 'id'})


class StableOrderingFilter(filters.OrderingFilter):
    """
    ``OrderingFilter`` that appends the primary key as a tiebreaker, so paginated
    results stay stable when the ordered values repeat (same role, same name...).
    """

    def filter(self, qs, value):
        qs = super().filter(qs, value)
        if not value:
            return qs
        ordering = list(qs.query.order_by)
        if any(
            isinstance(field, str) and field.lstrip('-') in TIEBREAKER_FIELDS
            for field in ordering
        ):
            return qs
        return qs.order_by(*ordering, 'pk')


def orderable_filter_factory(
    serializer_class: type[BaseSerializer],
    filterset_class: type[filterset.FilterSet] = filterset.FilterSet,
) -> type[filterset.FilterSet]:
    if 'order_by' in filterset_class.declared_filters:
        return filterset_class

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
            'order_by': StableOrderingFilter(
                choices=serializer_class.orderable_fields_choices
            ),
        },
    )
