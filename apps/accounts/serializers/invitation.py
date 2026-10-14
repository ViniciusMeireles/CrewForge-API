from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.choices import InvitationErrorMessages
from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.organization import Organization
from apps.accounts.serializers.mixins import ValidateRoleSerializerMixin
from apps.accounts.serializers.options import assignable_role_choices

User = get_user_model()


class InvitationOrganizationSerializer(serializers.ModelSerializer):
    description = serializers.CharField(source='profile.description', read_only=True)
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ['id', 'name', 'description', 'logo_url']
        read_only_fields = fields

    @classmethod
    def get_logo_url(cls, obj) -> str | None:
        profile = getattr(obj, '_profile', None) or obj.get_profile()
        logo = profile.get_logo_obj(dark_priority=False) if profile else None
        if logo and logo.image:
            return logo.image.file_url
        return None


class InvitationSerializer(
    ValidateRoleSerializerMixin, ModelSerializerMixin, serializers.ModelSerializer
):
    send_email = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
    )
    is_former_member = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            'id',
            'email',
            'is_expired',
            'is_accepted',
            'is_declined',
            'expired_at',
            'declined_at',
            'accepted_at',
            'role',
            'role_label',
            'organization',
            'last_email_sent_at',
            'send_email',
            'is_former_member',
        ]
        read_only_fields = ModelSerializerMixin._default_read_only_fields + [
            'id',
            'organization',
            'is_accepted',
            'is_declined',
            'declined_at',
            'accepted_at',
            'last_email_sent_at',
        ]
        extra_kwargs = {
            'role_label': {'read_only': True, 'source': 'get_role_display'},
        }
        options_extra_kwargs = {
            'role': {'choices_filter': assignable_role_choices},
        }

    def validate_email(self, value):
        if value and not self.instance:
            invitation_queryset = Invitation.objects.filter(
                email=value,
                is_active=True,
                is_expired=False,
                is_accepted=False,
                is_declined=False,
                organization_id=self.auth_organization_id,
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
            if organization.members.filter(user__email=email, is_active=True).exists():
                email_errors = errors.get('email', [])
                email_errors.append(
                    InvitationErrorMessages.USER_ALREADY_MEMBER.label,
                )
                errors['email'] = email_errors
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_former_member(self, obj) -> bool:
        if hasattr(obj, 'is_former_member'):
            return bool(obj.is_former_member)
        return bool(
            Invitation.objects.filter(pk=obj.pk)
            .annotate_former_member()
            .values_list('is_former_member', flat=True)
            .first()
        )

    def create(self, validated_data):
        send_email = validated_data.pop('send_email', False)
        instance: Invitation = super().create(validated_data)
        if send_email and instance.is_acceptable()[0]:
            instance.send_email()
        return instance


RECEIVED_INVITATION_FIELDS = [
    field for field in InvitationSerializer.Meta.fields if field != 'is_former_member'
]


class InvitationReceivedDetailSerializer(InvitationSerializer):
    organization = InvitationOrganizationSerializer(read_only=True)
    is_former_member = None

    class Meta(InvitationSerializer.Meta):
        fields = RECEIVED_INVITATION_FIELDS


class InvitationReceivedSerializer(InvitationSerializer):
    organization_name = serializers.CharField(
        read_only=True,
        source='organization.name',
        allow_null=True,
    )
    is_former_member = None

    class Meta(InvitationSerializer.Meta):
        fields = RECEIVED_INVITATION_FIELDS + ['key', 'organization_name']
        read_only_fields = fields


class InvitationByKeySerializer(serializers.ModelSerializer):
    organization = InvitationOrganizationSerializer(read_only=True)
    has_user = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            'key',
            'email',
            'organization',
            'has_user',
        ]
        read_only_fields = fields

    @classmethod
    def get_has_user(cls, obj) -> bool:
        return obj.get_user() is not None


class InvitationAcceptSerializer(serializers.Serializer):
    nickname = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
    )
