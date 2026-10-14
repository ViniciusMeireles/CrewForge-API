from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.models.member import Member
from apps.accounts.serializers.member import MemberUpdateSerializer


class MemberAdmitTestCase(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.user = UserFactory()

    def _admit(self, **kwargs):
        defaults = {
            'user': self.user,
            'organization': self.organization,
            'role': MemberRoleChoices.MEMBER,
        }
        defaults.update(kwargs)
        return Member.objects.admit(**defaults)

    def test_creates_new_member(self):
        member, readmitted = self._admit(nickname='neo')
        self.assertFalse(readmitted)
        self.assertTrue(member.is_active)
        self.assertEqual(member.nickname, 'neo')
        self.assertIsNotNone(member.joined_at)

    def test_reactivates_removed_member(self):
        removed = MemberFactory(
            user=self.user,
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
            is_active=False,
        )
        member, readmitted = self._admit()
        self.assertTrue(readmitted)
        self.assertEqual(member.pk, removed.pk)
        self.assertTrue(member.is_active)
        self.assertEqual(member.role, MemberRoleChoices.MEMBER)

    def test_active_member_raises(self):
        MemberFactory(user=self.user, organization=self.organization)
        with self.assertRaises(ValueError):
            self._admit()

    def test_blank_nickname_is_stored_as_none(self):
        member, _ = self._admit(nickname='')
        self.assertIsNone(member.nickname)

    def test_taken_nickname_raises_and_keeps_member_removed(self):
        MemberFactory(organization=self.organization, nickname='neo')
        removed = MemberFactory(
            user=self.user,
            organization=self.organization,
            is_active=False,
        )
        with self.assertRaises(ValidationError) as context:
            self._admit(nickname='neo')
        self.assertIn('nickname', context.exception.message_dict)
        removed.refresh_from_db()
        self.assertFalse(removed.is_active)

    def test_joined_at_is_read_only_on_update(self):
        self.assertIn('joined_at', MemberUpdateSerializer.Meta.read_only_fields)
