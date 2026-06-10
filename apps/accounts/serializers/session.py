from rest_framework import serializers

from apps.accounts.models.member import Member
from apps.accounts.serializers.organization import OrganizationListSerializer
from apps.accounts.serializers.user import UserReadySerializer


class MemberPermissionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = [
            'is_owner',
            'is_admin',
            'is_manager',
            'is_member',
            'has_owner_permission',
            'has_admin_permission',
            'has_manager_permission',
            'has_member_permission',
        ]


class MemberSessionSerializer(serializers.ModelSerializer):
    permissions = MemberPermissionsSerializer(source='*', read_only=True)

    class Meta:
        model = Member
        fields = ['id', 'role', 'nickname', 'permissions', 'last_login_at']


class SessionSerializer(serializers.Serializer):
    user = UserReadySerializer()
    organizations = OrganizationListSerializer(many=True, read_only=True)
    organization = OrganizationListSerializer(allow_null=True, default=None)
    member = MemberSessionSerializer(allow_null=True, default=None)
