from django_filters import filters, filterset
from rest_framework.serializers import BaseSerializer

from apps.generics.mixins.serializers import ModelSerializerFieldsMixin


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
            'order_by': filters.OrderingFilter(
                choices=serializer_class.orderable_fields_choices
            ),
        },
    )
