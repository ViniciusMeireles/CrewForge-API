from django.db import transaction
from rest_framework import serializers

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization, OrganizationProfile
from apps.generics.utils.shortcuts import get_object_or_none
from apps.generics.utils.strings import str_to_bool


class OrganizationReadySerializer(ModelSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            'id',
            'name',
            'slug',
        ]
        read_only_fields = fields


class OrganizationProfileListRelatedSerializer(
    ModelSerializerMixin,
    serializers.ModelSerializer,
):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationProfile
        fields = ['id', 'logo_url']

    def get_logo_url(self, obj: OrganizationProfile) -> str | None:
        logo = obj.get_logo_obj(
            dark_priority=str_to_bool(
                value=self.context.get('request').GET.get('dark_logo', 'false')
            )
        )
        if logo and logo.image:
            return logo.image.file_url
        return None


class OrganizationListSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    """Serializer for the Organization model."""

    profile = OrganizationProfileListRelatedSerializer()

    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'profile']
        read_only_fields = fields


class OrganizationProfileDetailRelatedSerializer(
    OrganizationProfileListRelatedSerializer
):
    class Meta:
        model = OrganizationProfile
        fields = ['id', 'website', 'description', 'logo_url']


class OrganizationDetailSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    profile = OrganizationProfileDetailRelatedSerializer(read_only=True)

    class Meta:
        model = Organization
        fields = '__all__'


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

    @transaction.atomic
    def save(self, **kwargs):
        profile_data = self._validated_data.pop('profile', {}) or {}
        creating = not bool(self.instance)
        instance: Organization = super().save(**kwargs)
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
        instance.get_profile()
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
