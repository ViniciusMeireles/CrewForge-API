from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.mixins.serializers import ModelSerializerMixin
from apps.teams.models.team import Team
from apps.teams.services import add_team_owner


class TeamSerializer(ModelSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = '__all__'
        read_only_fields = [
            *ModelSerializerMixin._default_read_only_fields,
            'organization',
            'slug',
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs=attrs)
        if 'name' not in attrs:
            return attrs
        if not (slug := slugify(attrs['name'])):
            raise serializers.ValidationError(
                {'name': [_('The name must contain at least one letter or number.')]}
            )
        teams_queryset = Team.objects.filter(
            organization_id=self.auth_organization_id,
            slug=slug,
            is_active=True,
        )
        if self.instance:
            teams_queryset = teams_queryset.exclude(pk=self.instance.pk)
        if teams_queryset.exists():
            raise serializers.ValidationError(
                {'name': [_('This team already exists.')]}
            )
        attrs['slug'] = slug
        return attrs

    def create(self, validated_data):
        """Create a new team."""
        instance = super().create(validated_data)
        add_team_owner(team=instance, member=self.auth_member, user=self.auth_user)
        return instance


class TeamListSerializer(TeamSerializer):
    member_count = serializers.IntegerField(read_only=True)
