from rest_framework import serializers

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.member import Member
from apps.teams.models.team_member import TeamMember


class OverviewMemberSerializer(serializers.ModelSerializer):
    role_label = serializers.CharField(read_only=True, source='get_role_display')

    class Meta:
        model = Member
        fields = ['id', 'role', 'role_label', 'created_at', 'joined_at']


class RoleCountSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=MemberRoleChoices.choices)
    role_label = serializers.CharField()
    count = serializers.IntegerField()


class RecentMemberSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.full_name')
    email = serializers.EmailField(source='user.email')
    role_label = serializers.CharField(read_only=True, source='get_role_display')

    class Meta:
        model = Member
        fields = [
            'id',
            'full_name',
            'email',
            'nickname',
            'role',
            'role_label',
            'created_at',
            'joined_at',
        ]


class MembersSectionSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_role = RoleCountSerializer(many=True)
    recent = RecentMemberSerializer(many=True)


class MyTeamSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='team_id')
    name = serializers.CharField(source='team.name')
    slug = serializers.CharField(source='team.slug')
    role_label = serializers.CharField(read_only=True, source='get_role_display')
    member_count = serializers.IntegerField()

    class Meta:
        model = TeamMember
        fields = ['id', 'name', 'slug', 'role', 'role_label', 'member_count']


class TeamsSectionSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    mine_count = serializers.IntegerField()
    mine = MyTeamSerializer(many=True)


class ExpiringInvitationSerializer(serializers.ModelSerializer):
    role_label = serializers.CharField(read_only=True, source='get_role_display')

    class Meta:
        model = Invitation
        fields = ['id', 'email', 'role', 'role_label', 'expired_at']


class InvitationsSectionSerializer(serializers.Serializer):
    pending = serializers.IntegerField()
    expiring_soon = ExpiringInvitationSerializer(many=True)


class ReceivedInvitationsSectionSerializer(serializers.Serializer):
    pending = serializers.IntegerField()


class OverviewSerializer(serializers.Serializer):
    generated_at = serializers.DateTimeField()
    member = OverviewMemberSerializer()
    members = MembersSectionSerializer(allow_null=True)
    teams = TeamsSectionSerializer(allow_null=True)
    invitations = InvitationsSectionSerializer(allow_null=True)
    received_invitations = ReceivedInvitationsSectionSerializer()
