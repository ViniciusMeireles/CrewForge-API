from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.mixins.serializers import ModelSerializerMixin

User = get_user_model()


class UserReadySerializer(ModelSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
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

    def create(self, validated_data):
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
