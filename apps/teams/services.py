from django.utils.translation import gettext_lazy as _

from apps.accounts.models.member import Member
from apps.accounts.models.user import User
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.models.team import Team
from apps.teams.models.team_member import TeamMember

LAST_OWNER_MESSAGE = _('The team must keep at least one owner.')


class LastTeamOwnerError(Exception):
    pass


def add_team_owner(*, team: Team, member: Member, user: User) -> TeamMember:
    return TeamMember.objects.create(
        member=member,
        team=team,
        role=TeamMemberRoleChoices.OWNER,
        created_by=user,
        updated_by=user,
    )


def ensure_team_keeps_owner(*, team_member: TeamMember) -> None:
    if team_member.is_last_owner:
        raise LastTeamOwnerError(LAST_OWNER_MESSAGE)
