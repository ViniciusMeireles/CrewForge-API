from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.mixins.serializers import ModelSerializerMixin

User = get_user_model()


class UserProfileSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
        ]
        read_only_fields = ['id', 'username']


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        style={'input_type': 'password'},
    )

    default_error_messages = {
        'incorrect_password': _('Current password is incorrect.'),
        'same_password': _('New password must be different from current password.'),
    }

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(
                self.default_error_messages['incorrect_password'],
                code='incorrect_password',
            )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs=attrs)
        if attrs.get('current_password') == attrs.get('new_password'):
            raise serializers.ValidationError(
                self.default_error_messages['same_password'],
                code='same_password',
            )
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user
