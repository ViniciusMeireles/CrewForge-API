from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.models.member import Member
from apps.accounts.serializers.mixins import (
    UserTokenSerializerMixin,
    ValidateRoleSerializerMixin,
)
from apps.accounts.serializers.user import UserGetOrCreateSerializer, UserSerializer


class MemberModelSerializer(
    ValidateRoleSerializerMixin, ModelSerializerMixin, serializers.ModelSerializer
):
    """Serializer for the Member model."""

    user = UserGetOrCreateSerializer()

    class Meta:
        model = Member
        fields = '__all__'
        read_only_fields = ModelSerializerMixin._default_read_only_fields + [
            'organization'
        ]

    def validate_user(self, value):
        """Validate that the user is not already a member of the organization."""
        user_name_field = get_user_model().USERNAME_FIELD
        user_name_value = value.get(user_name_field)
        filters = {f'user__{user_name_field}': user_name_value}
        if self.auth_organization:
            filters.update({'organization_id': self.auth_organization_id})
        else:
            filters.update({'organization_id__isnull': False})
        member = Member.objects.filter(**filters).first()
        if value and not self.instance and member:
            raise serializers.ValidationError(
                _('User is already a member of the organization.')
            )
        return value

    def save(self, **kwargs):
        user_data = self.validated_data.pop('user', {})
        user_serializer = self.fields['user']
        if self.instance:
            kwargs['user'] = user_serializer.update(self.instance.user, user_data)
        else:
            kwargs['user'] = user_serializer.create(user_data)

        instance = super().save(**kwargs)
        return instance


class MemberWithInviteCreateSerializer(UserTokenSerializerMixin, MemberModelSerializer):
    """Serializer for creating the Member model."""

    def save(self, **kwargs):
        instance = super().save(**kwargs)
        self.set_tokens_for_user(instance.user)
        return instance


class MemberUpdateSerializer(MemberModelSerializer):
    """Serializer for updating the Member model."""

    user = UserSerializer()

    class Meta(MemberModelSerializer.Meta):
        read_only_fields = MemberModelSerializer.Meta.read_only_fields + ['role']
        extra_kwargs = {
            'user': {
                'required': False,
                'help_text': _(
                    'User data to update, if not provided, will not update the user.'
                ),
            },
        }


class MemberRoleUpdateSerializer(
    ValidateRoleSerializerMixin, ModelSerializerMixin, serializers.ModelSerializer
):
    """Serializer for updating the role of a member."""

    class Meta:
        model = Member
        fields = ['role']
