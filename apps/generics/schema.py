from drf_spectacular.openapi import AutoSchema as SpectacularAutoSchema
from rest_framework.serializers import ModelSerializer

from apps.generics.serializers.options import OptionsSerializer
from apps.generics.tokens import AUTH_TOKEN_FIELD, TOKEN_FIELDS


def _is_body_token(name: str, schema: dict) -> bool:
    if name == AUTH_TOKEN_FIELD:
        return True
    return name in TOKEN_FIELDS and schema.get('type') == 'string'


class AutoSchema(SpectacularAutoSchema):
    """Response components require what is always rendered.

    Model serializers render every declared field. Tokens are the exception: the
    cookie transport moves them out of the body.
    """

    def _map_basic_serializer(self, serializer, direction):
        component = super()._map_basic_serializer(serializer, direction)
        if (
            direction == 'response'
            and component.get('properties')
            and isinstance(serializer, ModelSerializer)
            and not isinstance(serializer, OptionsSerializer)
        ):
            component['required'] = sorted(component['properties'])
        if direction == 'response' and component.get('required'):
            properties = component['properties']
            component['required'] = [
                name
                for name in component['required']
                if not _is_body_token(name, properties[name])
            ]
            if not component['required']:
                del component['required']
        return component
