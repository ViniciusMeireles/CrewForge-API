from django.test import TestCase

from apps.teams.choices import TeamMemberRoleChoices


class TeamMemberRoleChoicesTestCase(TestCase):
    def test_enum_values_count(self):
        values = list(TeamMemberRoleChoices.values)
        self.assertEqual(len(values), 4)

    def test_enum_values(self):
        self.assertEqual(TeamMemberRoleChoices.OWNER, 'owner')
        self.assertEqual(TeamMemberRoleChoices.ADMIN, 'admin')
        self.assertEqual(TeamMemberRoleChoices.MANAGER, 'manager')
        self.assertEqual(TeamMemberRoleChoices.MEMBER, 'member')

    def test_enum_labels(self):
        self.assertEqual(str(TeamMemberRoleChoices.OWNER.label), 'Owner')
        self.assertEqual(str(TeamMemberRoleChoices.ADMIN.label), 'Admin')
        self.assertEqual(str(TeamMemberRoleChoices.MANAGER.label), 'Manager')
        self.assertEqual(str(TeamMemberRoleChoices.MEMBER.label), 'Member')
