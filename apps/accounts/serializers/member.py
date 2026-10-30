from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
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
from apps.accounts.serializers.options import assignable_role_choices
from apps.accounts.serializers.user import UserSerializer
from apps.generics.mixins.serializers import ModelSerializerFieldsMixin

User = get_user_model()


def get_context_invitation(serializer) -> Invitation:
    context = serializer.context
    if 'invitation' not in context:
        invitation_key = (
            context.get('request')
            .parser_context.get('kwargs')
            .get(INVITATION_LOOKUP_URL_KWARG)
        )
        context['invitation'] = Invitation.objects.get(key=invitation_key)
    return context['invitation']


class UserCreateWithInviteSerializer(UserSerializer):
    auth_token = UserTokenSerializer(source='*', read_only=True)
    cookie_transport_fields = ('auth_token',)

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
            'password': {'write_only': True, 'required': True},
            'auth_token': {'read_only': True},
        }

    def get_password_user(self, attrs):
        user = super().get_password_user(attrs)
        user.email = get_context_invitation(self).email
        return user

    def validate(self, attrs):
        attrs = super().validate(attrs=attrs)
        is_acceptable, message = get_context_invitation(self).is_acceptable()
        if not is_acceptable:
            raise serializers.ValidationError(detail=message)
        return attrs


class MemberModelSerializer(
    ValidateRoleSerializerMixin,
    ModelSerializerMixin,
    ModelSerializerFieldsMixin,
    serializers.ModelSerializer,
):
    """Serializer for the Member model."""

    user = UserSerializer()
    role_label = serializers.CharField(read_only=True, source='get_role_display')

    class Meta:
        model = Member
        fields = '__all__'
        read_only_fields = ModelSerializerMixin._default_read_only_fields + [
            'organization',
            'last_login_at',
            'joined_at',
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


class MemberWithInviteCreateSerializer(MemberModelSerializer):
    """Serializer for creating the Member model."""

    user = UserCreateWithInviteSerializer()

    class Meta(MemberModelSerializer.Meta):
        read_only_fields = MemberModelSerializer.Meta.read_only_fields + ['role']

    @transaction.atomic
    def save(self, **kwargs):
        invitation = get_context_invitation(self)
        user = self.fields['user'].create(
            {
                **self.validated_data['user'],
                'email': invitation.email,
                'email_verified_at': timezone.now(),
            }
        )
        kwargs.update(
            {
                'user': user,
                'role': invitation.role,
                'organization_id': invitation.organization_id,
            }
        )
        instance = super().save(**kwargs)
        invitation.accept(member=instance, check=False)
        return instance


class UserUpdateSerializer(UserSerializer):
    """Read-only User of a Member update: identity is changed by the User only."""

    class Meta(UserSerializer.Meta):
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = fields


class MemberUpdateSerializer(MemberModelSerializer):
    """Serializer for updating the Member model."""

    user = UserUpdateSerializer(read_only=True)

    class Meta(MemberModelSerializer.Meta):
        read_only_fields = MemberModelSerializer.Meta.read_only_fields + ['role']


class MemberRoleUpdateSerializer(
    ValidateRoleSerializerMixin, ModelSerializerMixin, serializers.ModelSerializer
):
    """Serializer for updating the role of a member."""

    class Meta:
        model = Member
        fields = ['role']
        options_extra_kwargs = {
            'role': {'choices_filter': assignable_role_choices},
        }
