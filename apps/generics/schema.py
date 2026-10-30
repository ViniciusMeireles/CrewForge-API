from drf_spectacular.openapi import AutoSchema as SpectacularAutoSchema
from rest_framework.serializers import ModelSerializer

from apps.generics.serializers.options import OptionsSerializer


class AutoSchema(SpectacularAutoSchema):
    """Response components require what is always rendered.

    Model serializers render every declared field, except the
    ``cookie_transport_fields`` that the cookie transport moves out of the body.
    """

    def _map_basic_serializer(self, serializer, direction):
        component = super()._map_basic_serializer(serializer, direction)
        if direction != 'response' or not component.get('properties'):
            return component
        if isinstance(serializer, ModelSerializer) and not isinstance(
            serializer, OptionsSerializer
        ):
            component['required'] = sorted(component['properties'])
        optional = set(getattr(serializer, 'cookie_transport_fields', ()))
        if optional and component.get('required'):
            component['required'] = [
                name for name in component['required'] if name not in optional
            ]
            if not component['required']:
                del component['required']
        return component
