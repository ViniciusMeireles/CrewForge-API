from drf_spectacular.openapi import AutoSchema as SpectacularAutoSchema
from rest_framework.serializers import ModelSerializer

from apps.generics.serializers.options import OptionsSerializer


class AutoSchema(SpectacularAutoSchema):
    """Response components require what is always rendered.

    Model serializers render every declared field, except the
    ``cookie_transport_fields`` that the cookie transport moves out of the body.
    Options routes take their texts, parameters and response from the ViewSet.
    """

    def _get_options_schema(self) -> dict:
        get_options_schema = getattr(self.view, 'get_options_schema', None)
        return get_options_schema() if get_options_schema else {}

    def get_tags(self):
        return self._get_options_schema().get('tags') or super().get_tags()

    def get_summary(self):
        return self._get_options_schema().get('summary') or super().get_summary()

    def get_description(self):
        options_schema = self._get_options_schema()
        return options_schema.get('description') or super().get_description()

    def get_override_parameters(self):
        options_schema = self._get_options_schema()
        return options_schema.get('parameters') or super().get_override_parameters()

    def get_response_serializers(self):
        options_schema = self._get_options_schema()
        return options_schema.get('responses') or super().get_response_serializers()

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
