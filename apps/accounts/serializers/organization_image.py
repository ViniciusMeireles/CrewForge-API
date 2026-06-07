from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.serializers import SerializerMetaclass

from apps.accounts.choices import StoredFileAccess
from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.models.files import StoredFile
from apps.accounts.models.organization import OrganizationImage, OrganizationProfile
from apps.accounts.serializers.files import StoredFileListModelSerializer


class StoredFileOrgImageSerializer(
    StoredFileListModelSerializer,
    metaclass=SerializerMetaclass,
):
    class Meta:
        model = StoredFile
        update_fields = [
            'file',
            'name',
        ]
        read_only_fields = [
            'uuid',
            'original_name',
            'content_type',
            'size',
            'file_url',
            'download_name',
        ]
        fields = update_fields + read_only_fields
        extra_kwargs = {
            'file': {'write_only': True, 'required': True},
        }

    def save(self, **kwargs):
        kwargs.update(
            {
                'viewing_permission': StoredFileAccess.PUBLIC,
                'updating_permission': StoredFileAccess.ADMINS_ORGANIZATION,
                'organization_id': self.auth_organization_id,
                'owner': self.auth_user,
            }
        )
        instance = super().save(**kwargs)
        return instance


class OrganizationImageSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    image = StoredFileOrgImageSerializer(required=True)

    class Meta:
        model = OrganizationImage
        fields = ['id', 'image_type', 'image']
        read_only_fields = ModelSerializerMixin._default_read_only_fields

    def _get_org_profile(self) -> OrganizationProfile | None:
        if org := self.auth_organization:
            return org.get_profile()
        return None

    def validate_image_type(self, value: str) -> str:
        if not value:
            return value
        if org_profile := self._get_org_profile():
            if org_profile.images.filter(image_type=value).exists():
                raise serializers.ValidationError(
                    detail=_('An image of this type already exists for this profile.'),
                    code='invalid_image_type',
                )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs=attrs)
        if org_profile := self._get_org_profile():
            attrs.update({'profile': org_profile})
        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        if image_data := self.validated_data.pop('image', None):
            image_serializer = StoredFileOrgImageSerializer(
                data=image_data,
                context=self.context,
                instance=self.instance.image if self.instance else None,
                partial=self.partial,
            )
            if not image_serializer.is_valid():
                raise serializers.ValidationError(
                    detail={
                        'image': image_serializer.errors,
                    },
                    code='invalid_image',
                )
            image_obj = image_serializer.save()
            self._validated_data.update({'image': image_obj})
        return super().save(**kwargs)
