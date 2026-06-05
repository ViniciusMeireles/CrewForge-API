import mimetypes
from collections import defaultdict
from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.fields import ChoiceField
from rest_framework.serializers import SerializerMetaclass

from apps.accounts.choices import StoredFileAccess
from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.models.files import StoredFile
from apps.accounts.serializers.organization import OrganizationReadySerializer
from apps.accounts.serializers.user import UserReadySerializer


class StoredFileListModelSerializer(
    ModelSerializerMixin,
    serializers.ModelSerializer,
):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = StoredFile
        _fields = [
            'uuid',
            'name',
            'original_name',
            'content_type',
            'size',
            'file_url',
            'updated_at',
        ]
        _properties = ['download_name']
        fields = _fields + _properties
        read_only_fields = _fields

    def get_file_url(self, instance) -> str | None:
        request = self.context.get('request')
        if not request:
            return None
        return request.build_absolute_uri(instance.file_path)


class StoredFileDetailModelSerializer(
    StoredFileListModelSerializer,
    metaclass=SerializerMetaclass,
):
    owner = UserReadySerializer(required=False, allow_null=True)
    organization = OrganizationReadySerializer(required=False, allow_null=True)

    class Meta:
        model = StoredFile
        fields = StoredFileListModelSerializer.Meta.fields + [
            'viewing_permission',
            'updating_permission',
            'owner',
            'organization',
        ]
        read_only_fields = fields


class StoredFileCreateUpdateModelSerializer(
    StoredFileListModelSerializer,
    metaclass=SerializerMetaclass,
):
    class Meta:
        model = StoredFile
        update_fields = [
            'file',
            'name',
            'viewing_permission',
            'updating_permission',
            'owner',
            'organization',
        ]
        read_only_fields = list(
            set(StoredFileDetailModelSerializer.Meta.read_only_fields)
            - set(update_fields)
            - {'file'}
        )
        fields = update_fields + read_only_fields
        extra_kwargs = {
            'file': {'write_only': True, 'required': True},
        }

    def validate_organization(self, value) -> int | None:
        auth_member = self.auth_member
        if not value and auth_member:
            return auth_member.organization_id
        return value

    def _validate_updating_permission(
        self,
        attrs: dict[str, Any],
        errors: defaultdict[str, set],
    ):
        updating_permission = attrs.get('updating_permission')
        viewing_permission = attrs.get('viewing_permission')

        if (
            viewing_permission is None
            and 'viewing_permission' not in attrs.keys()
            and self.instance
        ):
            viewing_permission = self.instance.viewing_permission
        if (
            updating_permission is None
            and 'updating_permission' not in attrs.keys()
            and self.instance
        ):
            updating_permission = self.instance.updating_permission

        if updating_permission is None or viewing_permission is None:
            return None

        invalid_choice_msg = ChoiceField.default_error_messages.get('invalid_choice')
        for permission, levels in StoredFileAccess.permissions_levels_updating.items():
            if (
                permission == StoredFileAccess.PUBLIC
                and updating_permission == StoredFileAccess.PUBLIC
                and viewing_permission not in levels
            ) or (
                permission == viewing_permission and updating_permission not in levels
            ):
                errors['updating_permission'].add(
                    invalid_choice_msg.format(input=permission)
                )
                break
        return None

    def _validate_viewing_permission(
        self,
        attrs: dict[str, Any],
        errors: defaultdict[str, set],
    ):
        viewing_permission = attrs.get('viewing_permission')
        if viewing_permission is None:
            return None
        auth_user = self.auth_user

        invalid_choice_msg = ChoiceField.default_error_messages.get(
            'invalid_choice'
        ).format(input=viewing_permission)
        if not auth_user and viewing_permission == StoredFileAccess.PUBLIC:
            return None

        auth_member = self.auth_member
        if not auth_member and viewing_permission in [
            StoredFileAccess.PUBLIC,
            StoredFileAccess.OWNER,
        ]:
            return None

        if max_org_level := StoredFileAccess.max_org_level(member=auth_member):
            allowed_permissions = StoredFileAccess.permissions_levels_viewing.get(
                max_org_level, []
            )
            if viewing_permission in allowed_permissions:
                return None

        errors['viewing_permission'].add(invalid_choice_msg)
        return None

    def validate(self, attrs):
        attrs = super().validate(attrs=attrs)
        required_message = serializers.Field.default_error_messages.get('required')
        owner = attrs.get('owner')
        if owner is None and 'owner' not in attrs and self.instance:
            owner = self.instance.owner
        organization = attrs.get('organization') or self.auth_organization
        updating_permission = attrs.get(
            'updating_permission',
            getattr(self.instance, 'updating_permission', None),
        )
        viewing_permission = attrs.get(
            'viewing_permission',
            getattr(self.instance, 'viewing_permission', None),
        )
        access_types = [viewing_permission, updating_permission]

        errors = defaultdict(set)
        if owner and not owner.is_active:
            errors['owner'].add(_('Owner is not active.'))
        if (
            organization
            and not organization.is_active
            and (
                updating_permission in StoredFileAccess.organization_accesses
                or viewing_permission in StoredFileAccess.organization_accesses
            )
        ):
            errors['organization'].add(_('Organization is not active.'))

        for access in access_types:
            if access == StoredFileAccess.OWNER and not owner:
                errors['owner'].add(required_message)
            if (
                access
                in [
                    StoredFileAccess.OWNERS_ORGANIZATION,
                    StoredFileAccess.ADMINS_ORGANIZATION,
                    StoredFileAccess.MANAGERS_ORGANIZATION,
                    StoredFileAccess.MEMBERS_ORGANIZATION,
                ]
                and not organization
            ):
                errors['organization'].add(required_message)

        self._validate_updating_permission(attrs=attrs, errors=errors)
        self._validate_viewing_permission(attrs=attrs, errors=errors)

        if errors:
            raise serializers.ValidationError(errors)

        if (
            not (file := attrs.get('file'))
            and self.context
            and self.context.get('request')
        ):
            file = self.context.get('request').FILES.get('file')
        if file and (original_name := file.name.split('/')[-1]):
            guessed_type, __ = mimetypes.guess_type(original_name)
            content_type = guessed_type or 'application/octet-stream'
            size = file.size
            attrs.update(
                {
                    'content_type': content_type,
                    'original_name': original_name,
                    'size': size,
                }
            )
        return attrs

    def to_representation(self, instance):
        return StoredFileDetailModelSerializer(instance, context=self.context).data
