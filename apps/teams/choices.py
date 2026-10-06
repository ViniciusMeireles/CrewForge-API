from django.db import models
from django.utils.translation import gettext_lazy as _


class TeamMemberRoleChoices(models.TextChoices):
    OWNER = 'owner', _('Owner')
    ADMIN = 'admin', _('Admin')
    MANAGER = 'manager', _('Manager')
    MEMBER = 'member', _('Member')

    @classmethod
    def assignable_by(cls, member, team) -> list[str]:
        """
        Team roles the given member may assign in ``team``: every role for an
        organization manager+ (any team) or the team owner, manager/member for a
        team admin, none otherwise. Without a team only the organization rule
        applies.
        """
        if member is None:
            return []
        if member.has_manager_permission:
            return list(cls.values)
        if team is None or (team_member := team.get_active_team_member(member)) is None:
            return []
        if team_member.is_owner:
            return list(cls.values)
        if team_member.is_admin:
            return [cls.MANAGER, cls.MEMBER]
        return []
