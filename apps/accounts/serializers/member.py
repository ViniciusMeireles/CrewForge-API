from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.accounts.consts import INVITATION_LOOKUP_URL_KWARG
from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.accounts.serializers.auth import UserTokenSerializer
from apps.accounts.serializers.mixins import (
    ValidateRoleSerializerMixin,
)
from apps.accounts.serializers.user import UserGetOrCreateSerializer, UserSerializer

User = get_user_model()


class UserCreateWithInviteSerializer(UserSerializer):
    auth_token = UserTokenSerializer(source='*', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'password',
            'auth_token',
        ]
        extra_kwargs = {
            'email': {'read_only': True},
            'password': {'write_only': True, 'required': False},
            'auth_token': {'read_only': True},
        }

    def _get_invitation(self) -> Invitation:
        invitation_key = (
            self.context.get('request')
            .parser_context.get('kwargs')
            .get(INVITATION_LOOKUP_URL_KWARG)
        )
        return Invitation.objects.get(key=invitation_key)

    def validate(self, attrs):
        attrs = super().validate(attrs=attrs)
        invitation = self._get_invitation()
        is_acceptable, message = invitation.is_acceptable()
        if not is_acceptable:
            raise serializers.ValidationError(detail=message)
        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        invitation = self._get_invitation()
        kwargs.update({'email': invitation.email})
        instance = super().save(**kwargs)
        return instance


class MemberModelSerializer(
    ValidateRoleSerializerMixin, ModelSerializerMixin, serializers.ModelSerializer
):
    """Serializer for the Member model."""

    user = UserGetOrCreateSerializer()

    class Meta:
        model = Member
        fields = '__all__'
        read_only_fields = ModelSerializerMixin._default_read_only_fields + [
            'organization',
            'last_login_at',
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

    @transaction.atomic
    def save(self, **kwargs):
        user_serializer = self.fields['user']
        user_serializer.initial_data = self.initial_data.get('user', {})
        user_serializer.partial = self.partial
        user_serializer._context = self.context
        if self.instance and self.instance.user_id:
            user_serializer.instance = self.instance.user
        user_serializer.is_valid(raise_exception=True)

        kwargs['user'] = user_serializer.save()
        instance = super().save(**kwargs)
        return instance


class MemberWithInviteCreateSerializer(MemberModelSerializer):
    """Serializer for creating the Member model."""

    user = UserCreateWithInviteSerializer()

    class Meta(MemberModelSerializer.Meta):
        read_only_fields = MemberModelSerializer.Meta.read_only_fields + ['role']

    def _get_invitation(self) -> Invitation:
        invitation_key = (
            self.context.get('request')
            .parser_context.get('kwargs')
            .get(INVITATION_LOOKUP_URL_KWARG)
        )
        return Invitation.objects.get(key=invitation_key)

    @transaction.atomic
    def save(self, **kwargs):
        invitation = self._get_invitation()
        kwargs.update({'role': invitation.role})
        instance = super().save(**kwargs)
        invitation.accept(member=instance, check=False)
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
