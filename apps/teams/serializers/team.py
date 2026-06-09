from django.db import transaction
from rest_framework import serializers

from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.models.team import Team
from apps.teams.models.team_member import TeamMember


class TeamSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = '__all__'
        read_only_fields = ModelSerializerMixin._default_read_only_fields + [
            'organization'
        ]

    def create(self, validated_data):
        """Create a new team."""
        with transaction.atomic():
            instance = super().create(validated_data)
            TeamMember.objects.create(
                member=self.auth_member,
                team=instance,
                role=TeamMemberRoleChoices.OWNER,
                created_by=self.auth_user,
                updated_by=self.auth_user,
            )
        return instance
