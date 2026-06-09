from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.generics.utils.models import get_verbose_name_field
from apps.generics.utils.shortcuts import get_object_or_none


class UserReadySerializer(ModelSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = fields


class UserSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    """Serializer for creating a user."""

    class Meta:
        model = get_user_model()
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

    @staticmethod
    def _user_already_message():
        """Return a message indicating that the user already exists."""
        user_model = get_user_model()
        username_field = user_model.USERNAME_FIELD
        return _(
            'User with this %(username)s already exists.'
            % {'username': get_verbose_name_field(user_model, username_field)}
        )

    def is_valid(self, *, raise_exception=False):
        """
        Override the is_valid method to skip validation if the user already exists.
        """
        super().is_valid(raise_exception=False)
        errors = {}

        user_model = get_user_model()
        username_field = user_model.USERNAME_FIELD
        username_value = self.validated_data.get(username_field)
        if (
            username_value
            and (
                instance := get_object_or_none(
                    user_model, **{username_field: username_value}
                )
            )
            and not (self.auth_user and self.auth_user == instance)
        ):
            errors.update({username_field: self._user_already_message()})
            if isinstance(self._errors, dict):
                self._errors.update(errors)
            elif isinstance(self._errors, list):
                self._errors.append(errors)

        if self._errors and raise_exception:
            raise ValidationError(self.errors)
        elif errors and raise_exception:
            raise ValidationError(errors)

        return not bool(self._errors) and not bool(errors)

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


class UserGetOrCreateSerializer(UserSerializer):
    """Serializer for getting or creating a user."""

    def is_valid(self, *, raise_exception=False):
        """
        Override the is_valid method to skip validation if the user already exists.
        """
        super().is_valid(raise_exception=False)
        errors = {}

        user_model = get_user_model()
        username_field = user_model.USERNAME_FIELD
        username_value = self.validated_data.get(username_field)
        if username_value and (
            instance := get_object_or_none(
                user_model, **{username_field: username_value}
            )
        ):
            if self.auth_user:
                self.instance = instance
                return True
            errors.update({username_field: self._user_already_message()})
            if isinstance(self._errors, dict):
                self._errors.update(errors)
            elif isinstance(self._errors, list):
                self._errors.append(errors)

        if self._errors and raise_exception:
            raise ValidationError(self.errors)
        elif errors and raise_exception:
            raise ValidationError(errors)

        return not bool(self._errors) and not bool(errors)

    def save(self, **kwargs):
        if self.instance:
            return self.instance
        return super().save(**kwargs)
