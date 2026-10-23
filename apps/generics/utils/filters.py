from django.utils.translation import gettext_lazy as _
from django_filters import filters, filterset
from rest_framework.exceptions import ValidationError
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


class PeriodValidationMixin:
    period_fields: tuple[str, ...] = ()

    def filter_queryset(self, queryset):
        data = self.form.cleaned_data
        for name in self.period_fields:
            period = data.get(name)
            if period and period.start and period.stop and period.start > period.stop:
                raise ValidationError(
                    {name: [_('The start date must be before the end date.')]}
                )
        return super().filter_queryset(queryset)
