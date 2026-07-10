from django.db import IntegrityError
from django.test import TestCase

from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.models.team_member import TeamMember


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

    def test_filter_actives(self):
        TeamMemberFactory()
        TeamMemberFactory(is_active=False)
        active_count = TeamMember.objects.filter(is_active=True).count()
        self.assertEqual(active_count, 1)

    def test_get_or_none(self):
        tm = TeamMemberFactory()
        result = TeamMember.objects.get_or_none(id=tm.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, tm.id)

    def test_default_role(self):
        tm = TeamMemberFactory()
        self.assertEqual(tm.role, TeamMemberRoleChoices.MEMBER)

    def test_default_is_active(self):
        tm = TeamMemberFactory()
        self.assertTrue(tm.is_active)

    def test_ordering(self):
        tm1 = TeamMemberFactory()
        tm2 = TeamMemberFactory()
        queryset = TeamMember.objects.all()
        self.assertEqual(queryset[0], tm2)
        self.assertEqual(queryset[1], tm1)
