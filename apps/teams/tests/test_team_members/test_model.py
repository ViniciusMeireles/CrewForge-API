from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.choices import MemberRoleChoices
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

    def test_unique_team_member_allows_reuse_after_soft_delete(self):
        tm = TeamMemberFactory()
        tm.inactivate()
        other = TeamMemberFactory(
            team=tm.team,
            member=tm.member,
            organization=tm.team.organization,
        )
        self.assertNotEqual(tm.id, other.id)


class TeamMemberRolePropertiesTestCase(TestCase):
    def _team_member(self, role, member_role=MemberRoleChoices.MEMBER):
        team_member = TeamMemberFactory(role=role)
        team_member.member.role = member_role
        return team_member

    def test_role_flags(self):
        flags = ('is_owner', 'is_admin', 'is_manager', 'is_member')
        for role, flag in zip(TeamMemberRoleChoices, flags, strict=True):
            with self.subTest(role=role):
                team_member = self._team_member(role)
                self.assertEqual(
                    {name: getattr(team_member, name) for name in flags},
                    {name: name == flag for name in flags},
                )

    def test_permission_hierarchy(self):
        expected = {
            TeamMemberRoleChoices.OWNER: (True, True, True, True),
            TeamMemberRoleChoices.ADMIN: (False, True, True, True),
            TeamMemberRoleChoices.MANAGER: (False, False, True, True),
            TeamMemberRoleChoices.MEMBER: (False, False, False, True),
        }
        for role, permissions in expected.items():
            with self.subTest(role=role):
                team_member = self._team_member(role)
                self.assertEqual(
                    (
                        team_member.has_owner_permission,
                        team_member.has_admin_permission,
                        team_member.has_manager_permission,
                        team_member.has_member_permission,
                    ),
                    permissions,
                )

    def test_organization_admin_has_team_owner_permission(self):
        team_member = self._team_member(
            TeamMemberRoleChoices.MEMBER, member_role=MemberRoleChoices.ADMIN
        )
        self.assertTrue(team_member.has_owner_permission)

    def test_label_expression(self):
        team_member = TeamMemberFactory(member__nickname='Zorro')
        label = (
            TeamMember.objects.filter(pk=team_member.pk)
            .annotate(label=TeamMember.label_expression())
            .values_list('label', flat=True)
            .get()
        )
        self.assertIn('Zorro', label)
