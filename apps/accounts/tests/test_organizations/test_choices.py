from django.test import TestCase

from apps.accounts.choices import MemberRoleChoices


class MemberRoleChoicesTestCase(TestCase):
    def test_enum_values_count(self):
        values = list(MemberRoleChoices.values)
        self.assertEqual(len(values), 4)

    def test_enum_values(self):
        self.assertEqual(MemberRoleChoices.OWNER, 'owner')
        self.assertEqual(MemberRoleChoices.ADMIN, 'admin')
        self.assertEqual(MemberRoleChoices.MANAGER, 'manager')
        self.assertEqual(MemberRoleChoices.MEMBER, 'member')

    def test_enum_labels(self):
        self.assertEqual(str(MemberRoleChoices.OWNER.label), 'Owner')
        self.assertEqual(str(MemberRoleChoices.ADMIN.label), 'Admin')
        self.assertEqual(str(MemberRoleChoices.MANAGER.label), 'Manager')
        self.assertEqual(str(MemberRoleChoices.MEMBER.label), 'Member')
