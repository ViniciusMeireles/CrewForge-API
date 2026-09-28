from django.db import IntegrityError
from django.test import TestCase

from apps.teams.factories.team_members import TeamMemberFactory


class TeamMemberModelTestCase(TestCase):
    def test_str(self):
        tm = TeamMemberFactory()
        expected = f'{tm.member} - {tm.team}'
        self.assertEqual(str(tm), expected)

    def test_unique_team_member_constraint(self):
        tm = TeamMemberFactory()
        with self.assertRaises(IntegrityError):
            TeamMemberFactory(
                team=tm.team,
                member=tm.member,
                organization=tm.team.organization,
            )

    def test_unique_team_member_allows_reuse_after_soft_delete(self):
        tm = TeamMemberFactory()
        tm.inactivate()
        other = TeamMemberFactory(
            team=tm.team,
            member=tm.member,
            organization=tm.team.organization,
        )
        self.assertNotEqual(tm.id, other.id)
