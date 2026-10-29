from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
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
        kwargs.setdefault(
            'replace_owner', kwargs.get('role') == MemberRoleChoices.OWNER
        )
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

    def test_superuser_member_sees_only_what_its_role_allows(self):
        member = self._new_member(role=MemberRoleChoices.MEMBER)
        member.user.is_superuser = True
        member.user.save(update_fields=['is_superuser'])
        self.assertEqual(self._visible_roles(member), set())


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


class InvitationQuerySetAlreadyMembersTestCase(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()

    def _acceptable_ids(self):
        return set(Invitation.objects.filter_acceptable().values_list('id', flat=True))

    def test_email_of_active_member_is_excluded(self):
        member = MemberFactory(organization=self.organization)
        invitation = InvitationFactory(
            organization=self.organization,
            email=member.user.email,
        )
        self.assertNotIn(invitation.id, self._acceptable_ids())

    def test_linked_user_active_member_is_excluded(self):
        member = MemberFactory(organization=self.organization)
        invitation = InvitationFactory(
            organization=self.organization,
            user=member.user,
        )
        self.assertNotIn(invitation.id, self._acceptable_ids())

    def test_removed_member_is_kept(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        invitation = InvitationFactory(
            organization=self.organization,
            email=member.user.email,
        )
        self.assertIn(invitation.id, self._acceptable_ids())

    def test_inactive_user_with_email_is_kept(self):
        member = MemberFactory(organization=self.organization)
        member.user.is_active = False
        member.user.save(update_fields=['is_active'])
        invitation = InvitationFactory(
            organization=self.organization,
            email=member.user.email,
        )
        self.assertIn(invitation.id, self._acceptable_ids())

    def test_member_of_another_organization_is_kept(self):
        member = MemberFactory()
        invitation = InvitationFactory(
            organization=self.organization,
            email=member.user.email,
        )
        self.assertIn(invitation.id, self._acceptable_ids())


class InvitationQuerySetInactiveOrganizationTestCase(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.user = UserFactory()
        self.invitation = InvitationFactory(
            organization=self.organization,
            email=self.user.email,
        )
        self.organization.is_active = False
        self.organization.save(update_fields=['is_active'])

    def test_not_acceptable(self):
        self.assertFalse(Invitation.objects.filter_acceptable().exists())

    def test_not_received(self):
        self.assertFalse(
            Invitation.objects.filter_received_by_user(self.user).exists(),
        )


class InvitationQuerySetFormerMemberTestCase(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()

    def _is_former_member(self, invitation):
        return (
            Invitation.objects.filter(pk=invitation.pk)
            .annotate_former_member()
            .values_list('is_former_member', flat=True)
            .get()
        )

    def test_removed_member_email_is_former_member(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        invitation = InvitationFactory(
            organization=self.organization,
            email=member.user.email,
        )
        self.assertTrue(self._is_former_member(invitation))

    def test_removed_member_linked_user_is_former_member(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        invitation = InvitationFactory(organization=self.organization, user=member.user)
        self.assertTrue(self._is_former_member(invitation))

    def test_active_member_is_not_former_member(self):
        member = MemberFactory(organization=self.organization)
        invitation = InvitationFactory(
            organization=self.organization,
            email=member.user.email,
        )
        self.assertFalse(self._is_former_member(invitation))

    def test_never_member_is_not_former_member(self):
        invitation = InvitationFactory(organization=self.organization)
        self.assertFalse(self._is_former_member(invitation))

    def test_removed_member_of_another_organization_is_not_former_member(self):
        member = MemberFactory(is_active=False)
        invitation = InvitationFactory(
            organization=self.organization,
            email=member.user.email,
        )
        self.assertFalse(self._is_former_member(invitation))

    def test_inactive_user_with_the_email_is_not_former_member(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        member.user.is_active = False
        member.user.save(update_fields=['is_active'])
        invitation = InvitationFactory(
            organization=self.organization,
            email=member.user.email,
        )
        self.assertFalse(self._is_former_member(invitation))
