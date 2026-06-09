from rest_framework import serializers

from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.models.organization import OrganizationProfile


class OrganizationProfileSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = OrganizationProfile
        fields = ['id', 'website', 'description', 'organization']
        read_only_fields = ModelSerializerMixin._default_read_only_fields + [
            'organization',
        ]
