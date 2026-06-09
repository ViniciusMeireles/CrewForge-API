from django.db import transaction
from rest_framework import serializers

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization, OrganizationProfile
from apps.generics.utils.shortcuts import get_object_or_none


class OrganizationReadySerializer(ModelSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            'id',
            'name',
            'slug',
        ]
        read_only_fields = fields


class OrganizationListSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    """Serializer for the Organization model."""

    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'profile']


class OrganizationProfileRelatedSerializer(
    ModelSerializerMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = OrganizationProfile
        fields = ['id', 'website', 'description']


class OrganizationSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    """Serializer for the Organization model."""

    profile = OrganizationProfileRelatedSerializer(required=False)

    class Meta:
        model = Organization
        fields = '__all__'
        read_only_fields = ModelSerializerMixin._default_read_only_fields + ['owner']

    def _get_profile_serializer(self, data) -> OrganizationProfileRelatedSerializer:
        profile_instance = None
        if self.instance:
            profile_instance = get_object_or_none(
                model_class=OrganizationProfile, organization=self.instance
            )
        return OrganizationProfileRelatedSerializer(
            data=data,
            context=self.context,
            partial=self.partial,
            instance=profile_instance,
        )

    @transaction.atomic()
    def save(self, **kwargs):
        profile_data = self._validated_data.pop('profile', {}) or {}
        creating = not bool(self.instance)
        instance = super().save(**kwargs)
        if creating:
            member = Member.objects.create(
                user=self.auth_user,
                organization=instance,
                role=MemberRoleChoices.OWNER,
                created_by=self.auth_user,
                updated_by=self.auth_user,
            )
            instance.owner = member
            instance.save(update_fields=['owner'])
        if profile_data:
            profile_serializer = self._get_profile_serializer(profile_data)
            if not profile_serializer.is_valid():
                raise serializers.ValidationError(
                    detail={
                        'profile': profile_serializer.errors,
                    },
                    code='invalid_profile',
                )
            profile_serializer.save(**{'organization': instance} if creating else {})
        return instance
