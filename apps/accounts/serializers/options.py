from django.core.exceptions import ImproperlyConfigured

from apps.accounts.fields import PaginatedOptionsActiveOrganizationSerializer
from apps.generics.fields.options import PaginatedOptionsBaseSerializer
from apps.generics.serializers.options import OptionsModelSerializer


class OptionsOrganizationModelSerializer(
    OptionsModelSerializer,
):
    """
    Options serializer whose relations are scoped to the session organization.

    A relation to a model without ``organization_id`` cannot be scoped and would
    list records from every tenant, so building such a field raises
    ``ImproperlyConfigured`` (at class creation, through the ViewSet metaclass)
    unless the source serializer declares it as global with
    ``Meta.options_extra_kwargs = {'<field>': {'organization_scoped': False}}``.
    """

    serializer_related_field = PaginatedOptionsActiveOrganizationSerializer

    def get_fields(self):
        fields = super().get_fields()
        extra_kwargs = self.get_extra_kwargs()
        for field_name, field in fields.items():
            if not isinstance(field, PaginatedOptionsBaseSerializer):
                continue
            model = field.queryset.model
            if hasattr(model, 'organization_id'):
                continue
            if extra_kwargs.get(field_name, {}).get('organization_scoped') is False:
                continue
            raise ImproperlyConfigured(
                f'{self.__class__.__name__}.{field_name}: form options for '
                f'{model.__name__} cannot be scoped to the session organization '
                '(the model has no organization_id) and would list records from '
                'every tenant. Disable the routes (options_actions = ()), declare '
                'the field as a nested serializer on the source, or mark it as '
                "global with Meta.options_extra_kwargs = {'"
                f"{field_name}': {{'organization_scoped': False}}}}."
            )
        return fields
