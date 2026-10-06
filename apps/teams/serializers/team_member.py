from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.fields import empty

from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.accounts.models.member import Member
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.models.team_member import TeamMember
from apps.teams.serializers.options import (
    assignable_team_role_choices,
    exclude_team_members,
)

LAST_OWNER_MESSAGE = _('The team must keep at least one owner.')


class TeamMemberDetailSerializer(serializers.ModelSerializer):
    """Organization member data shown in team member lists."""

    full_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    role_label = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = Member
        fields = ['id', 'full_name', 'email', 'nickname', 'role', 'role_label']
        read_only_fields = fields


class TeamMemberSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    """Serializer for the TeamMember model."""

    member_detail = TeamMemberDetailSerializer(source='member', read_only=True)
    role_label = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = TeamMember
        fields = '__all__'
        read_only_fields = ModelSerializerMixin._default_read_only_fields
        options_extra_kwargs = {
            'team': {'label_field_name': 'name'},
            'member': {
                'label_field_name': Member.label_expression(),
                'queryset_filter': exclude_team_members,
            },
            'role': {'choices_filter': assignable_team_role_choices},
        }

    @property
    def is_adding(self) -> bool:
        """Creating a team member or reactivating a removed one."""
        return self.instance is None or not self.instance.is_active

    def validate_team(self, value):
        """Only who manages the team may add members to it."""
        if value:
            if self.instance and value != self.instance.team:
                raise serializers.ValidationError(_('Not allowed to change the team.'))
            if self.is_adding and not value.can_manage_members(self.auth_member):
                raise serializers.ValidationError(
                    _('You are not allowed to add a member to this team.')
                )
        return value

    def validate_member(self, value):
        """Validate that the member is not already associated with the team."""
        if value and self.instance and value != self.instance.member:
            raise serializers.ValidationError(_('Not allowed to change the member.'))
        return value

    def run_validation(self, initial_data=empty):
        """
        Run validation on the serializer data and "recreate" the instance if needed.
        """
        team_member = None
        if initial_data and isinstance(initial_data, dict) and not self.instance:
            team_member = TeamMember.objects.filter(
                team=initial_data.get('team'),
                member=initial_data.get('member'),
                is_active=False,
            ).first()
            self.instance = team_member
        data = super().run_validation(initial_data)
        if team_member:
            data.update({'is_active': True})
        return data

    def validate(self, attrs):
        attrs = super().validate(attrs)
        team = attrs.get('team') or self.instance.team
        if self.is_adding:
            attrs.setdefault('role', TeamMemberRoleChoices.MEMBER)
        role = attrs.get('role', self.instance and self.instance.role)
        if role not in TeamMemberRoleChoices.assignable_by(self.auth_member, team):
            raise serializers.ValidationError(
                {'role': [_('Not allowed to set the %(role)s role.') % {'role': role}]}
            )
        if (
            not self.is_adding
            and role != TeamMemberRoleChoices.OWNER
            and self.instance.is_last_owner
        ):
            raise serializers.ValidationError({'role': [LAST_OWNER_MESSAGE]})
        team_member = TeamMember.objects.filter(
            team=team,
            member=attrs.get('member'),
        ).first()
        if team_member and (self.instance is None or team_member != self.instance):
            raise serializers.ValidationError(
                _('This member is already part of the team.')
            )
        return attrs


class TeamMemberUpdateSerializer(TeamMemberSerializer):
    """Serializer for updating a TeamMember."""

    class Meta(TeamMemberSerializer.Meta):
        read_only_fields = TeamMemberSerializer.Meta.read_only_fields + [
            'team',
            'member',
        ]
        fields = TeamMemberSerializer.Meta.fields
