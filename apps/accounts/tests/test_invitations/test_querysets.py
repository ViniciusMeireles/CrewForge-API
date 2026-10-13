from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.models.invitation import Invitation


class InvitationQuerySetVisibleToTestCase(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        for role in MemberRoleChoices.values:
            InvitationFactory(organization=self.organization, role=role)

    def _visible_roles(self, member):
        return set(
            Invitation.objects.filter_visible_to(member).values_list(
                'role',
                flat=True,
            ),
        )

    def _new_member(self, **kwargs):
        return MemberFactory(organization=self.organization, **kwargs)

    def test_none_member_returns_empty(self):
        self.assertFalse(Invitation.objects.filter_visible_to(None).exists())

    def test_manager_sees_nothing(self):
        member = self._new_member(role=MemberRoleChoices.MANAGER)
        self.assertEqual(self._visible_roles(member), set())

    def test_member_sees_nothing(self):
        member = self._new_member(role=MemberRoleChoices.MEMBER)
        self.assertEqual(self._visible_roles(member), set())

    def test_admin_sees_manager_and_member(self):
        member = self._new_member(role=MemberRoleChoices.ADMIN)
        self.assertEqual(
            self._visible_roles(member),
            {MemberRoleChoices.MANAGER, MemberRoleChoices.MEMBER},
        )

    def test_owner_sees_all_roles(self):
        member = self._new_member(role=MemberRoleChoices.OWNER)
        self.assertEqual(self._visible_roles(member), set(MemberRoleChoices.values))

    def test_inactive_member_returns_empty(self):
        member = self._new_member(role=MemberRoleChoices.ADMIN, is_active=False)
        self.assertEqual(self._visible_roles(member), set())

    def test_superuser_member_sees_all_roles(self):
        member = self._new_member(role=MemberRoleChoices.MEMBER)
        member.user.is_superuser = True
        member.user.save(update_fields=['is_superuser'])
        self.assertEqual(self._visible_roles(member), set(MemberRoleChoices.values))


class InvitationQuerySetAcceptableBoundaryTestCase(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.now = timezone.now()

    def test_expired_at_equal_to_now_is_not_acceptable(self):
        InvitationFactory(organization=self.organization, expired_at=self.now)
        self.assertFalse(Invitation.objects.filter_acceptable().exists())

    def test_expired_at_after_now_is_acceptable(self):
        InvitationFactory(
            organization=self.organization,
            expired_at=self.now + timedelta(seconds=1),
        )
        self.assertTrue(Invitation.objects.filter_acceptable().exists())

    def test_expired_at_in_the_past_is_not_acceptable(self):
        InvitationFactory(
            organization=self.organization,
            expired_at=self.now - timedelta(seconds=1),
        )
        self.assertFalse(Invitation.objects.filter_acceptable().exists())
