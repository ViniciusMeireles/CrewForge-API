from apps.accounts.fields import PaginatedOptionsActiveOrganizationSerializer
from apps.generics.serializers.options import OptionsModelSerializer


class OptionsOrganizationModelSerializer(
    OptionsModelSerializer,
):
    """Options serializer whose relations are scoped to the session organization."""

    serializer_related_field = PaginatedOptionsActiveOrganizationSerializer
