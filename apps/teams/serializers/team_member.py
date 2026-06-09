from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.fields import empty

from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.teams.models.team_member import TeamMember


class TeamMemberSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    """Serializer for the TeamMember model."""

    class Meta:
        model = TeamMember
        fields = '__all__'
        read_only_fields = ModelSerializerMixin._default_read_only_fields

    def validate_team(self, value):
        """Validate that the team is not already associated with the member."""
        if value:
            if self.instance and value != self.instance.team:
                raise serializers.ValidationError(_('Not allowed to change the team.'))
            if (
                self.auth_member
                and not value.is_team_member(self.auth_member)
                and not self.auth_member.has_manager_permission
            ):
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
        team_member = TeamMember.objects.filter(
            team=attrs.get('team'),
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
