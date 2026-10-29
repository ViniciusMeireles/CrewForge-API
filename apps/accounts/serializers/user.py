from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.utils.language import current_language

User = get_user_model()


def validate_new_password(password: str, user) -> None:
    try:
        password_validation.validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc


class UserReadySerializer(ModelSerializerMixin, serializers.ModelSerializer):
    email_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'email_verified',
            'first_name',
            'last_name',
        ]
        read_only_fields = fields


class StoredFileOwnerSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']
        read_only_fields = fields


class UserSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    """Serializer for creating a user."""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'password']
        read_only_fields = ['id']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
        }

    def validate_password(self, value):
        """Validate that the password is not empty."""
        if not value and self.instance:
            raise serializers.ValidationError(_('Password cannot be empty.'))
        elif value and self.instance and self.instance != self.auth_user:
            raise serializers.ValidationError(_('Not allowed to change the password.'))
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        password = attrs.get('password')
        if not self.instance and not password:
            raise serializers.ValidationError(
                {'password': [_('Password is required.')]}
            )
        if password:
            fields = ('username', 'email', 'first_name', 'last_name')
            user = self.instance or User(
                **{field: attrs.get(field) or '' for field in fields}
            )
            try:
                validate_new_password(password, user)
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({'password': exc.detail}) from exc
        return attrs

    def create(self, validated_data):
        validated_data.setdefault('preferred_language', current_language())
        password = validated_data.pop('password', None)
        instance = super().create(validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=['password'])
        return instance

    def update(self, instance, validated_data):
        """Update a user instance."""
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=['password'])
        return instance
