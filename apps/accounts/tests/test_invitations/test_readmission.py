from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import (
    InvitationErrorMessages,
    MemberErrorMessages,
    MemberRoleChoices,
)
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.models.member import Member
from apps.accounts.tests.mixins import APITestCaseMixin


class InvitationReadmissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.user = UserFactory()
        self.old_login = timezone.now() - timedelta(days=30)
        self.removed = MemberFactory(
            user=self.user,
            organization=self.organization,
            role=MemberRoleChoices.MANAGER,
            nickname='bob',
            is_active=False,
            last_login_at=self.old_login,
        )
        self.old_joined_at = self.removed.joined_at
        self.invitation = InvitationFactory(
            organization=self.organization,
            email=self.user.email,
            role=MemberRoleChoices.MEMBER,
        )
        self.client.force_authenticate(user=self.user)

    def _accept(self, invitation=None, **data):
        invitation = invitation or self.invitation
        url = reverse(
            'accounts:invitations-accept',
            kwargs={'invitation_pk': invitation.pk},
        )
        return self.client.post(url, data=data, format='json')

    def test_readmission_reactivates_the_same_member(self):
        response = self._accept(nickname='bobby')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data['readmitted'])
        self.assertEqual(response.data['member_id'], self.removed.pk)
        memberships = Member.objects.filter(
            user=self.user,
            organization=self.organization,
        )
        self.assertEqual(memberships.count(), 1)
        self.removed.refresh_from_db()
        self.assertTrue(self.removed.is_active)
        self.assertEqual(self.removed.role, MemberRoleChoices.MEMBER)
        self.assertEqual(self.removed.nickname, 'bobby')
        self.assertGreater(self.removed.joined_at, self.old_joined_at)
        self.assertEqual(self.removed.last_login_at, self.old_login)

    def test_readmission_links_and_accepts_the_invitation(self):
        original = InvitationFactory(
            organization=self.organization,
            email=self.user.email,
            is_accepted=True,
            member=self.removed,
        )
        response = self._accept()
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.invitation.refresh_from_db()
        original.refresh_from_db()
        self.assertTrue(self.invitation.is_accepted)
        self.assertEqual(self.invitation.member_id, self.removed.pk)
        self.assertEqual(original.member_id, self.removed.pk)

    def test_readmission_without_nickname_clears_the_old_one(self):
        response = self._accept()
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.removed.refresh_from_db()
        self.assertIsNone(self.removed.nickname)

    def test_readmission_keeps_the_old_nickname_when_requested_again(self):
        response = self._accept(nickname='bob')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.removed.refresh_from_db()
        self.assertEqual(self.removed.nickname, 'bob')

    def test_nickname_taken_by_another_member_returns_400(self):
        MemberFactory(organization=self.organization, nickname='bobby')
        response = self._accept(nickname='bobby')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['error']['details']['nickname'],
            [MemberErrorMessages.NICKNAME_TAKEN.label],
        )
        self.removed.refresh_from_db()
        self.invitation.refresh_from_db()
        self.assertFalse(self.removed.is_active)
        self.assertFalse(self.invitation.is_accepted)

    def test_nickname_taken_by_another_removed_member_returns_400(self):
        MemberFactory(organization=self.organization, nickname='bobby', is_active=False)
        response = self._accept(nickname='bobby')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_nickname_longer_than_limit_returns_400(self):
        response = self._accept(nickname='x' * 101)
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('nickname', response.data['error']['details'])
        self.removed.refresh_from_db()
        self.assertFalse(self.removed.is_active)

    def test_new_member_is_not_a_readmission(self):
        newcomer = UserFactory()
        invitation = InvitationFactory(
            organization=self.organization,
            email=newcomer.email,
        )
        self.client.force_authenticate(user=newcomer)
        response = self._accept(invitation)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['readmitted'])
        member = Member.objects.get(user=newcomer, organization=self.organization)
        self.assertIsNotNone(member.joined_at)

    def test_second_invitation_after_readmission_returns_400(self):
        self.assertEqual(self._accept().status_code, http_status.HTTP_200_OK)
        second = InvitationFactory(
            organization=self.organization,
            email=self.user.email,
        )
        response = self._accept(second)
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            InvitationErrorMessages.USER_ALREADY_MEMBER.label,
        )

    def test_readmission_is_logged(self):
        with self.assertLogs('security', level='INFO') as logs:
            self._accept()
        events = [record.security_event['event'] for record in logs.records]
        self.assertIn('member.readmitted', events)
        self.assertNotIn('invitation.accepted', events)

    def test_readmission_only_touches_the_invitation_organization(self):
        other = MemberFactory(user=self.user)
        self._accept()
        other.refresh_from_db()
        self.assertTrue(other.is_active)
        self.assertNotEqual(other.organization_id, self.organization.pk)
