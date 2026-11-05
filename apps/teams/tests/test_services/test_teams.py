from django.test import TestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.users import UserFactory
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.teams import TeamFactory
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.models.team import Team
from apps.teams.selectors import teams_with_member_count
from apps.teams.services import (
    LastTeamOwnerError,
    add_team_owner,
    ensure_team_keeps_owner,
)


class TeamServiceTestCase(TestCase):
    def setUp(self):
        self.team = TeamFactory()
        self.member = MemberFactory(organization=self.team.organization)

    def owner(self):
        return TeamMemberFactory(
            team=self.team, member=self.member, role=TeamMemberRoleChoices.OWNER
        )

    def test_add_team_owner(self):
        user = UserFactory()
        owner = add_team_owner(team=self.team, member=self.member, user=user)
        self.assertEqual(owner.role, TeamMemberRoleChoices.OWNER)
        self.assertEqual(owner.created_by, user)

    def test_last_owner_cannot_leave(self):
        with self.assertRaises(LastTeamOwnerError):
            ensure_team_keeps_owner(team_member=self.owner())

    def test_owner_with_a_co_owner_can_leave(self):
        owner = self.owner()
        TeamMemberFactory(
            team=self.team,
            member=MemberFactory(organization=self.team.organization),
            role=TeamMemberRoleChoices.OWNER,
        )
        ensure_team_keeps_owner(team_member=owner)

    def test_member_count_annotation(self):
        self.owner()
        team = teams_with_member_count(Team.objects.filter(pk=self.team.pk)).get()
        self.assertEqual(team.member_count, 1)
