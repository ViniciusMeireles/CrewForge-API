from django.contrib import admin

from apps.teams.models.team import Team
from apps.teams.models.team_member import TeamMember


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'organization', 'is_active', 'created_at')
    search_fields = ('name', 'slug', 'organization__name')
    list_filter = ('is_active', 'organization')
    readonly_fields = ('slug',)
    list_select_related = ('organization',)


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('team', 'member', 'role', 'is_active')
    list_filter = ('role', 'is_active', 'team__organization')
    search_fields = ('team__name', 'member__user__email', 'member__user__username')
    list_select_related = ('team', 'member__user', 'member__organization')
