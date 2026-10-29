from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory


class OverviewScopeTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.url = reverse('dashboard:overview')
        self.organization = self.new_account()
        self.member = self.organization.owner

    def _get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        return response.data

    def test_soft_deleted_member_not_counted(self):
        MemberFactory(organization=self.organization, is_active=False)
        data = self._get()
        self.assertEqual(data['members']['total'], 1)
        counts = {row['role']: row['count'] for row in data['members']['by_role']}
        self.assertEqual(counts[MemberRoleChoices.OWNER], 1)
        self.assertEqual(counts[MemberRoleChoices.MEMBER], 0)
        self.assertEqual(data['members']['recent'][0]['id'], self.member.id)

    def test_soft_deleted_team_not_counted(self):
        TeamFactory(organization=self.organization, is_active=False)
        self.assertEqual(self._get()['teams']['total'], 0)
        TeamFactory(organization=self.organization)
        self.assertEqual(self._get()['teams']['total'], 1)

    def test_soft_deleted_team_member_not_in_mine(self):
        team = TeamFactory(organization=self.organization)
        TeamMemberFactory(
            organization=self.organization,
            team=team,
            member=self.member,
            is_active=False,
        )
        data = self._get()
        self.assertEqual(data['teams']['total'], 1)
        self.assertEqual(data['teams']['mine_count'], 0)
        self.assertEqual(data['teams']['mine'], [])

    def test_non_pending_invitations_not_counted(self):
        owner_member = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.OWNER,
            replace_owner=True,
        )
        InvitationFactory(
            organization=self.organization,
            is_accepted=True,
        )
        InvitationFactory(
            organization=self.organization,
            is_declined=True,
        )
        InvitationFactory(
            organization=self.organization,
            is_expired=True,
        )
        InvitationFactory(
            organization=self.organization,
            expired_at=timezone.now() - timedelta(days=1),
        )
        InvitationFactory(
            organization=self.organization,
            is_active=False,
        )
        InvitationFactory(
            organization=self.organization,
            member=owner_member,
        )
        data = self._get()
        self.assertEqual(data['invitations']['pending'], 0)
        self.assertEqual(data['invitations']['expiring_soon'], [])

    def test_admin_sees_only_manager_and_member_invitations(self):
        now = timezone.now()
        for role in MemberRoleChoices.values:
            InvitationFactory(
                organization=self.organization,
                role=role,
                expired_at=now + timedelta(days=2),
            )
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        data = self._get()
        self.assertEqual(data['invitations']['pending'], 2)
        self.assertEqual(
            {row['role'] for row in data['invitations']['expiring_soon']},
            {MemberRoleChoices.MANAGER, MemberRoleChoices.MEMBER},
        )

    def test_owner_sees_every_role_invitation(self):
        for role in MemberRoleChoices.values:
            InvitationFactory(
                organization=self.organization,
                role=role,
            )
        data = self._get()
        self.assertEqual(data['invitations']['pending'], 4)

    def test_cross_organization_isolation(self):
        other = OrganizationFactory()
        MemberFactory(user=self.member.user, organization=other)
        MemberFactory(organization=other)
        TeamFactory(organization=other)
        InvitationFactory(organization=other)
        data = self._get()
        self.assertEqual(data['members']['total'], 1)
        self.assertEqual(data['teams']['total'], 0)
        self.assertEqual(data['teams']['mine_count'], 0)
        self.assertEqual(data['invitations']['pending'], 0)

    def test_received_counts_email_match_from_other_organization(self):
        other = OrganizationFactory()
        InvitationFactory(organization=other, email=self.member.user.email)
        data = self._get()
        self.assertEqual(data['received_invitations']['pending'], 1)

    def test_received_zero_when_email_unverified(self):
        user = UserFactory(email_verified_at=None)
        member = MemberFactory(
            user=user,
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=member)
        other = OrganizationFactory()
        InvitationFactory(organization=other, email=user.email)
        data = self._get()
        self.assertEqual(data['received_invitations']['pending'], 0)

    def test_received_excludes_organization_where_user_is_member(self):
        InvitationFactory(
            organization=self.organization,
            email=self.member.user.email,
        )
        data = self._get()
        self.assertEqual(data['received_invitations']['pending'], 0)

    def test_received_counts_organization_where_user_was_removed(self):
        other = OrganizationFactory()
        MemberFactory(user=self.member.user, organization=other, is_active=False)
        InvitationFactory(organization=other, email=self.member.user.email)
        data = self._get()
        self.assertEqual(data['received_invitations']['pending'], 1)

    def test_pending_excludes_invitation_to_existing_member(self):
        existing = MemberFactory(organization=self.organization)
        InvitationFactory(organization=self.organization, email=existing.user.email)
        data = self._get()
        self.assertEqual(data['invitations']['pending'], 0)
        self.assertEqual(data['invitations']['expiring_soon'], [])

    def test_received_excludes_inactive_organization(self):
        other = OrganizationFactory()
        InvitationFactory(organization=other, email=self.member.user.email)
        other.is_active = False
        other.save(update_fields=['is_active'])
        data = self._get()
        self.assertEqual(data['received_invitations']['pending'], 0)

    def test_received_excludes_declined_accepted_and_inactive(self):
        other = OrganizationFactory()
        email = self.member.user.email
        InvitationFactory(organization=other, email=email, is_declined=True)
        InvitationFactory(organization=other, email=email, is_accepted=True)
        InvitationFactory(organization=other, email=email, is_active=False)
        data = self._get()
        self.assertEqual(data['received_invitations']['pending'], 0)
