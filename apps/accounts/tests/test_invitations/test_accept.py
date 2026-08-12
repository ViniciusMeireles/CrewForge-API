from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import InvitationErrorMessages
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.models.member import Member
from apps.accounts.tests.mixins import APITestCaseMixin


class InvitationAcceptTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory.create()
        self.user = UserFactory()
        self.accept_url_name = 'accounts:invitations-accept'

    def _accept_url(self, invitation):
        return reverse(
            self.accept_url_name,
            kwargs={'invitation_pk': invitation.pk},
        )

    def _create_invitation(self, **kwargs):
        defaults = {
            'organization': self.organization,
            'email': self.user.email,
        }
        defaults.update(kwargs)
        return InvitationFactory(**defaults)

    def test_accept_creates_member_and_marks_accepted(self):
        invitation = self._create_invitation()
        self.client.force_authenticate(user=self.user)
        url = self._accept_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        invitation.refresh_from_db()
        self.assertTrue(invitation.is_accepted)
        self.assertIsNotNone(invitation.accepted_at)
        self.assertIsNotNone(invitation.member)
        member_exists = Member.objects.filter(
            user=self.user,
            organization=self.organization,
            role=invitation.role,
        ).exists()
        self.assertTrue(member_exists)

    def test_accept_sets_nickname_when_provided(self):
        invitation = self._create_invitation()
        self.client.force_authenticate(user=self.user)
        url = self._accept_url(invitation)
        response = self.client.post(url, data={'nickname': 'Johnny'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        member = Member.objects.get(user=self.user, organization=self.organization)
        self.assertEqual(member.nickname, 'Johnny')

    def test_accept_requires_authentication(self):
        invitation = self._create_invitation()
        url = self._accept_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_accept_requires_email_match(self):
        other_user = UserFactory()
        invitation = self._create_invitation()
        self.client.force_authenticate(user=other_user)
        url = self._accept_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_accept_fails_if_already_accepted(self):
        invitation = self._create_invitation(is_accepted=True)
        self.client.force_authenticate(user=self.user)
        url = self._accept_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            InvitationErrorMessages.INVITATION_ACCEPTED.label,
        )

    def test_accept_fails_if_already_declined(self):
        invitation = self._create_invitation(
            is_declined=True,
            declined_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.user)
        url = self._accept_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            InvitationErrorMessages.INVITATION_DECLINED.label,
        )

    def test_accept_fails_if_expired(self):
        invitation = self._create_invitation(
            is_expired=True,
            expired_at=timezone.now() - timedelta(days=1),
        )
        self.client.force_authenticate(user=self.user)
        url = self._accept_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            InvitationErrorMessages.INVITATION_EXPIRED.label,
        )

    def test_accept_fails_if_user_already_member(self):
        MemberFactory(
            user=self.user,
            organization=self.organization,
        )
        invitation = self._create_invitation()
        self.client.force_authenticate(user=self.user)
        url = self._accept_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            InvitationErrorMessages.USER_ALREADY_MEMBER.label,
        )

    def test_accept_returns_jwt_tokens(self):
        invitation = self._create_invitation()
        self.client.force_authenticate(user=self.user)
        url = self._accept_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('member_id', response.data)
        self.assertIsInstance(response.data['access'], str)
        self.assertIsInstance(response.data['refresh'], str)
        self.assertIsInstance(response.data['member_id'], int)
