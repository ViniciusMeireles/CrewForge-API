from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.accounts.serializers.organization import (
    OrganizationProfileDetailRelatedSerializer,
)
from apps.audit.serializers.audit_event import AuditEventSerializer
from apps.teams.models.team import Team

User = get_user_model()


class PlatformOverviewSerializer(serializers.Serializer):
    organizations_total = serializers.IntegerField()
    organizations_suspended = serializers.IntegerField()
    organizations_new_7d = serializers.IntegerField()
    organizations_new_30d = serializers.IntegerField()
    organizations_active_30d = serializers.IntegerField()
    users_total = serializers.IntegerField()
    users_blocked = serializers.IntegerField()
    users_new_7d = serializers.IntegerField()
    users_new_30d = serializers.IntegerField()


class PlatformUserRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    email = serializers.EmailField()


class PlatformOwnerSerializer(PlatformUserRefSerializer):
    member_id = serializers.IntegerField()
    member_since = serializers.DateTimeField()


class PlatformSuspensionSerializer(serializers.Serializer):
    suspended_at = serializers.DateTimeField()
    suspended_by = PlatformUserRefSerializer(allow_null=True)
    reason = serializers.CharField()


class PlatformOrganizationCountsSerializer(serializers.Serializer):
    active_members = serializers.IntegerField()
    teams = serializers.IntegerField()
    pending_invitations = serializers.IntegerField()


def user_ref(user) -> dict | None:
    if user is None:
        return None
    return {'id': user.pk, 'full_name': user.full_name, 'email': user.email}


class PlatformOrganizationListSerializer(serializers.ModelSerializer):
    owner = serializers.SerializerMethodField()
    active_members_count = serializers.IntegerField(read_only=True)
    last_access_at = serializers.DateTimeField(read_only=True, allow_null=True)
    is_deleted = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            'id',
            'name',
            'slug',
            'owner',
            'active_members_count',
            'created_at',
            'last_access_at',
            'status',
            'is_deleted',
        ]
        read_only_fields = fields

    @extend_schema_field(PlatformOwnerSerializer(allow_null=True))
    def get_owner(self, obj: Organization) -> dict | None:
        if not (member := obj.owner):
            return None
        return {
            **user_ref(member.user),
            'member_id': member.pk,
            'member_since': member.joined_at,
        }

    def get_is_deleted(self, obj) -> bool:
        return not obj.is_active


class PlatformOrganizationDetailSerializer(PlatformOrganizationListSerializer):
    profile = OrganizationProfileDetailRelatedSerializer(read_only=True)
    counts = serializers.SerializerMethodField()
    storage_bytes = serializers.IntegerField(read_only=True)
    suspension = serializers.SerializerMethodField()

    class Meta(PlatformOrganizationListSerializer.Meta):
        fields = PlatformOrganizationListSerializer.Meta.fields + [
            'profile',
            'counts',
            'storage_bytes',
            'suspension',
        ]
        read_only_fields = fields

    @extend_schema_field(PlatformOrganizationCountsSerializer)
    def get_counts(self, obj: Organization) -> dict:
        return {
            'active_members': obj.active_members_count,
            'teams': obj.teams_count,
            'pending_invitations': obj.pending_invitations_count,
        }

    @extend_schema_field(PlatformSuspensionSerializer(allow_null=True))
    def get_suspension(self, obj: Organization) -> dict | None:
        if not obj.is_suspended:
            return None
        return {
            'suspended_at': obj.suspended_at,
            'suspended_by': user_ref(obj.suspended_by),
            'reason': obj.suspension_reason,
        }


class PlatformMemberSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = ['id', 'user', 'role', 'joined_at', 'last_login_at', 'is_active']
        read_only_fields = fields

    @extend_schema_field(PlatformUserRefSerializer)
    def get_user(self, obj: Member) -> dict:
        return user_ref(obj.user)


class PlatformTeamSerializer(serializers.ModelSerializer):
    members_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Team
        fields = ['id', 'name', 'description', 'members_count', 'created_at']
        read_only_fields = fields


class PlatformInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ['id', 'email', 'role', 'expired_at', 'last_email_sent_at']
        read_only_fields = fields


class PlatformMembershipOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'status']
        read_only_fields = fields


class PlatformMembershipSerializer(serializers.ModelSerializer):
    organization = PlatformMembershipOrganizationSerializer(read_only=True)

    class Meta:
        model = Member
        fields = ['id', 'organization', 'role', 'is_active', 'joined_at']
        read_only_fields = fields


class PlatformBlockingSerializer(serializers.Serializer):
    blocked_at = serializers.DateTimeField()
    blocked_by = PlatformUserRefSerializer(allow_null=True)
    reason = serializers.CharField()


class PlatformUserListSerializer(serializers.ModelSerializer):
    email_verified = serializers.BooleanField(read_only=True)
    organizations_count = serializers.IntegerField(read_only=True)
    is_blocked = serializers.BooleanField(read_only=True)
    is_deleted = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'full_name',
            'email',
            'email_verified',
            'date_joined',
            'last_login',
            'organizations_count',
            'platform_role',
            'is_blocked',
            'is_deleted',
        ]
        read_only_fields = fields

    def get_is_deleted(self, obj) -> bool:
        return not obj.is_active


class PlatformUserDetailSerializer(PlatformUserListSerializer):
    blocking = serializers.SerializerMethodField()
    memberships = serializers.SerializerMethodField()
    can_impersonate = serializers.SerializerMethodField()
    can_block = serializers.SerializerMethodField()

    class Meta(PlatformUserListSerializer.Meta):
        fields = PlatformUserListSerializer.Meta.fields + [
            'blocking',
            'memberships',
            'can_impersonate',
            'can_block',
        ]
        read_only_fields = fields

    def _request_user(self):
        request = self.context.get('request')
        return getattr(request, 'user', None)

    @extend_schema_field(PlatformBlockingSerializer(allow_null=True))
    def get_blocking(self, obj) -> dict | None:
        if not obj.is_blocked:
            return None
        return {
            'blocked_at': obj.blocked_at,
            'blocked_by': user_ref(obj.blocked_by),
            'reason': obj.blocked_reason,
        }

    @extend_schema_field(PlatformMembershipSerializer(many=True))
    def get_memberships(self, obj) -> list[dict]:
        members = (
            Member.objects.filter(user=obj, organization__is_active=True)
            .select_related('organization')
            .order_by('organization__name', 'id')
        )
        return PlatformMembershipSerializer(members, many=True).data

    def get_can_impersonate(self, obj) -> bool:
        staff = self._request_user()
        return bool(
            staff
            and staff.pk != obj.pk
            and obj.is_active
            and not obj.is_blocked
            and not obj.is_platform_staff
        )

    def get_can_block(self, obj) -> bool:
        staff = self._request_user()
        return bool(
            staff and staff.is_platform_admin and staff.pk != obj.pk and obj.is_active
        )


class PlatformAuditOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name']
        read_only_fields = fields


class PlatformAuditEventSerializer(AuditEventSerializer):
    organization = PlatformAuditOrganizationSerializer(read_only=True, allow_null=True)

    class Meta(AuditEventSerializer.Meta):
        fields = AuditEventSerializer.Meta.fields + ['organization', 'subject_user']
        read_only_fields = fields
