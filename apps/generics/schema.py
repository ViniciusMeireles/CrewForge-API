from drf_spectacular.openapi import AutoSchema as SpectacularAutoSchema
from rest_framework.serializers import ModelSerializer

from apps.generics.serializers.options import OptionsSerializer


class AutoSchema(SpectacularAutoSchema):
    """Model serializers render every declared field, so their responses require all."""

    def _map_basic_serializer(self, serializer, direction):
        component = super()._map_basic_serializer(serializer, direction)
        if (
            direction == 'response'
            and component.get('properties')
            and isinstance(serializer, ModelSerializer)
            and not isinstance(serializer, OptionsSerializer)
        ):
            component['required'] = sorted(component['properties'])
        return component
