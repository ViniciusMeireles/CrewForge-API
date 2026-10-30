from drf_spectacular.openapi import AutoSchema as SpectacularAutoSchema

from apps.generics.serializers.options import OptionsSerializer


class AutoSchema(SpectacularAutoSchema):
    """Response components require every rendered field, except options subsets."""

    def _map_basic_serializer(self, serializer, direction):
        component = super()._map_basic_serializer(serializer, direction)
        if (
            direction == 'response'
            and component.get('properties')
            and not isinstance(serializer, OptionsSerializer)
        ):
            component['required'] = sorted(component['properties'])
        return component
