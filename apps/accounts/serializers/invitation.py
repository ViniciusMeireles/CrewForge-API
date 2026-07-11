from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.choices import InvitationErrorMessages
from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.models.invitation import Invitation
from apps.accounts.serializers.mixins import ValidateRoleSerializerMixin

User = get_user_model()


class InvitationSerializer(
    ValidateRoleSerializerMixin, ModelSerializerMixin, serializers.ModelSerializer
):
    send_email = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
    )

    class Meta:
        model = Invitation
        fields = [
            'id',
            'email',
            'is_expired',
            'is_accepted',
            'expired_at',
            'role',
            'organization',
            'last_email_sent_at',
            'send_email',
        ]
        read_only_fields = ModelSerializerMixin._default_read_only_fields + [
            'id',
            'organization',
            'is_accepted',
            'last_email_sent_at',
        ]

    def validate_email(self, value):
        if value and not self.instance:
            invitation_queryset = Invitation.objects.filter(
                email=value,
                is_active=True,
                is_expired=False,
                is_accepted=False,
            ).exclude(
                expired_at__lt=timezone.now(),
            )
            if invitation_queryset.exists():
                raise serializers.ValidationError(
                    _('An invitation with this email already exists.')
                )
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs=attrs)
        errors = {}
        if (expired_at := attrs.get('expired_at')) and expired_at < timezone.now():
            expired_at_errors = errors.get('expired_at', [])
            expired_at_errors.append(
                InvitationErrorMessages.INVITATION_EXPIRED.label,
            )
            errors['expired_at'] = expired_at_errors
        if (email := attrs.get('email')) and (organization := self.auth_organization):
            if organization.members.filter(user__email=email).exists():
                email_errors = errors.get('email', [])
                email_errors.append(
                    InvitationErrorMessages.USER_ALREADY_MEMBER.label,
                )
                errors['email'] = email_errors
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def create(self, validated_data):
        send_email = validated_data.pop('send_email', False)
        instance: Invitation = super().create(validated_data)
        if send_email and instance.is_acceptable()[0]:
            instance.send_email()
        return instance
