from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer as TokenObtainPairBaseSerializer,
)

from apps.accounts.serializers.mixins import UserTokenSerializerMixin
from apps.accounts.serializers.user import UserReadySerializer
from apps.accounts.utils.email_verification import email_verification_token

User = get_user_model()


class UserTokenSerializer(UserTokenSerializerMixin, serializers.ModelSerializer):
    AUTO_SET_TOKEN = True

    class Meta(UserTokenSerializerMixin.Meta):
        model = User
        fields = UserTokenSerializerMixin.Meta.fields
        read_only_fields = fields


class TokenObtainPairSerializer(
    UserTokenSerializerMixin,
    TokenObtainPairBaseSerializer,
):
    auth_user = serializers.SerializerMethodField()

    @extend_schema_field(UserReadySerializer)
    def get_auth_user(self, obj=None):
        """Return the user associated with the token."""
        if not hasattr(self, 'user') or not self.user:
            return None
        return UserReadySerializer(
            instance=self.user,
            context=self.context,
        ).data

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        attrs.update({'auth_user': self.get_auth_user()})
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    uid = serializers.SerializerMethodField()
    token = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self._uid = None
        self._token = None

    def get_uid(self, obj) -> str:
        """Return the UID for the user."""
        return self._uid

    def get_token(self, obj) -> str:
        """Return the token for the user."""
        return self._token

    def validate(self, attrs):
        """Find the active user of the email without revealing whether it exists."""
        self.user = User.objects.filter(
            email=attrs.get('email'), is_active=True
        ).first()
        if self.user:
            self._uid = urlsafe_base64_encode(force_bytes(self.user.pk))
            self._token = default_token_generator.make_token(self.user)
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(required=True, write_only=True)
    token = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None

    def validate(self, attrs):
        """Validate the UID and token."""
        uid = attrs.get('uid')
        token = attrs.get('token')

        try:
            uid_decoded = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=uid_decoded, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist) as err:
            raise serializers.ValidationError(_('Invalid UID.')) from err

        if not default_token_generator.check_token(user, token):
            raise serializers.ValidationError(_('Invalid token.'))
        self.user = user
        return attrs


class EmailVerificationConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(required=True, write_only=True)
    token = serializers.CharField(required=True, write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None

    def validate(self, attrs):
        try:
            user_pk = force_str(urlsafe_base64_decode(attrs.get('uid')))
            user = User.objects.get(pk=user_pk, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist) as err:
            raise serializers.ValidationError(_('Invalid verification link.')) from err

        if not email_verification_token.check_token(user, attrs.get('token')):
            raise serializers.ValidationError(_('Invalid verification link.'))
        self.user = user
        return attrs
