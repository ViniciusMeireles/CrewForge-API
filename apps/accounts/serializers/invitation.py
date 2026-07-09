from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.models.invitation import Invitation
from apps.accounts.serializers.mixins import ValidateRoleSerializerMixin


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

    def create(self, validated_data):
        send_email = validated_data.pop('send_email', False)
        instance: Invitation = super().create(validated_data)
        if send_email:
            instance.send_email()
            instance.last_email_sent_at = timezone.now()
            instance.save(update_fields=['last_email_sent_at', 'updated_at'])
        return instance
