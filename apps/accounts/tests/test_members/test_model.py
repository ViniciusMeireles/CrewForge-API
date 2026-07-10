from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.models.member import Member


class MemberModelTestCase(TestCase):
    def test_str(self):
        member = MemberFactory()
        expected = f'{member.user} - {member.organization}'
        self.assertEqual(str(member), expected)

    def test_label_expression(self):
        member = MemberFactory()
        expr = Member.label_expression()
        queryset = Member.objects.filter(id=member.id).annotate(label=expr)
        self.assertIsNotNone(queryset.first().label)

    def test_is_owner_true(self):
        member = MemberFactory(role=MemberRoleChoices.OWNER)
        self.assertTrue(member.is_owner)

    def test_is_owner_false_when_inactive(self):
        member = MemberFactory(role=MemberRoleChoices.OWNER, is_active=False)
        self.assertFalse(member.is_owner)

    def test_is_owner_false_for_member(self):
        member = MemberFactory(role=MemberRoleChoices.MEMBER)
        self.assertFalse(member.is_owner)

    def test_is_admin_true(self):
        member = MemberFactory(role=MemberRoleChoices.ADMIN)
        self.assertTrue(member.is_admin)

    def test_is_manager_true(self):
        member = MemberFactory(role=MemberRoleChoices.MANAGER)
        self.assertTrue(member.is_manager)

    def test_is_member_true(self):
        member = MemberFactory(role=MemberRoleChoices.MEMBER)
        self.assertTrue(member.is_member)

    def test_has_owner_permission(self):
        member = MemberFactory(role=MemberRoleChoices.OWNER)
        self.assertTrue(member.has_owner_permission)

    def test_has_owner_permission_inactive(self):
        member = MemberFactory(role=MemberRoleChoices.OWNER, is_active=False)
        self.assertFalse(member.has_owner_permission)

    def test_has_owner_permission_superuser(self):
        user = UserFactory(is_superuser=True)
        member = MemberFactory(user=user, role=MemberRoleChoices.MEMBER)
        self.assertTrue(member.has_owner_permission)

    def test_has_admin_permission_owner(self):
        member = MemberFactory(role=MemberRoleChoices.OWNER)
        self.assertTrue(member.has_admin_permission)

    def test_has_admin_permission_admin(self):
        member = MemberFactory(role=MemberRoleChoices.ADMIN)
        self.assertTrue(member.has_admin_permission)

    def test_has_admin_permission_manager(self):
        member = MemberFactory(role=MemberRoleChoices.MANAGER)
        self.assertFalse(member.has_admin_permission)

    def test_has_manager_permission_manager(self):
        member = MemberFactory(role=MemberRoleChoices.MANAGER)
        self.assertTrue(member.has_manager_permission)

    def test_has_manager_permission_member(self):
        member = MemberFactory(role=MemberRoleChoices.MEMBER)
        self.assertFalse(member.has_manager_permission)

    def test_has_member_permission_member(self):
        member = MemberFactory(role=MemberRoleChoices.MEMBER)
        self.assertTrue(member.has_member_permission)

    def test_permission_chain_inactive(self):
        member = MemberFactory(role=MemberRoleChoices.OWNER, is_active=False)
        self.assertFalse(member.has_owner_permission)
        self.assertFalse(member.has_admin_permission)
        self.assertFalse(member.has_manager_permission)
        self.assertFalse(member.has_member_permission)

    def test_unique_constraint_user_organization(self):
        member = MemberFactory()
        with self.assertRaises(IntegrityError):
            MemberFactory(
                user=member.user,
                organization=member.organization,
            )

    def test_unique_constraint_nickname_organization(self):
        member = MemberFactory()
        with self.assertRaises(IntegrityError):
            MemberFactory(
                nickname=member.nickname,
                organization=member.organization,
            )

    def test_unique_constraint_different_org_same_user(self):
        member = MemberFactory()
        MemberFactory(user=member.user)
        self.assertEqual(Member.objects.filter(user=member.user).count(), 2)

    def test_manager_get_or_none_found(self):
        member = MemberFactory()
        result = Member.objects.get_or_none(id=member.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, member.id)

    def test_manager_get_or_none_not_found(self):
        result = Member.objects.get_or_none(id=99999)
        self.assertIsNone(result)

    def test_ordering(self):
        MemberFactory()
        MemberFactory()
        queryset = Member.objects.all()
        ids = list(queryset.values_list('id', flat=True))
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_default_role(self):
        member = MemberFactory(role=MemberRoleChoices.MEMBER)
        self.assertEqual(member.role, MemberRoleChoices.MEMBER)

    def test_default_is_active(self):
        member = MemberFactory()
        self.assertTrue(member.is_active)

    def test_filter_actives(self):
        MemberFactory(is_active=True)
        MemberFactory(is_active=True)
        MemberFactory(is_active=False)
        active_ids = Member.objects.filter_actives().values_list('id', flat=True)
        self.assertEqual(len(active_ids), Member.objects.filter(is_active=True).count())
