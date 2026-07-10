from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import InvitationErrorMessages, MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class MemberCRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:members-list')
        self.choices_url = reverse('accounts:members-choices')
        self.create_with_invite_url_name = 'accounts:members-create-with-invite'
        self.update_role_url_name = 'accounts:members-update-role'

    def _detail_url(self, member):
        return reverse('accounts:members-detail', args=[member.id])

    def _member_payload(self, **overrides):
        user_data = UserFactory.build()
        member_data = MemberFactory.build()
        payload = {
            'user': {
                'username': user_data.username,
                'email': user_data.email,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name,
                'password': user_data.password,
            },
            'nickname': member_data.nickname,
        }
        payload.update(overrides)
        return payload

    def test_list_members(self):
        MemberFactory.create_batch(size=5, organization=self.organization)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 6)

    def test_list_only_active(self):
        MemberFactory(organization=self.organization, is_active=False)
        response = self.client.get(self.list_url)
        for result in response.data['results']:
            self.assertTrue(result['is_active'])

    def test_retrieve_member(self):
        member = MemberFactory(organization=self.organization)
        url = self._detail_url(member)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['id'], member.id)

    def test_retrieve_nonexistent(self):
        url = self._detail_url(MemberFactory.build(id=99999))
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_create_member_with_invite(self):
        user_data = UserFactory.build()
        invite = InvitationFactory.create(
            organization=self.organization,
            email=user_data.email,
            expired_at=None,
        )
        payload = self._member_payload(
            user__username=user_data.username,
            user__email=user_data.email,
        )
        url = reverse(self.create_with_invite_url_name, args=[invite.key])
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], invite.role)
        self.assertIsNotNone(response.data['user']['auth_token']['access'])

    def test_create_with_invite_expired_returns_404(self):
        user_data = UserFactory.build()
        invite = InvitationFactory.create(
            organization=self.organization,
            email=user_data.email,
            expired_at=timezone.now() - timezone.timedelta(days=1),
            is_expired=True,
        )
        payload = self._member_payload(
            user__username=user_data.username,
            user__email=user_data.email,
        )
        url = reverse(self.create_with_invite_url_name, args=[invite.key])
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data['detail'],
            InvitationErrorMessages.INVITATION_NOT_FOUND.label,
        )

    def test_create_with_invite_not_acceptable_returns_404(self):
        user_data = UserFactory.build()
        invite = InvitationFactory.create(
            organization=self.organization,
            email=user_data.email,
            expired_at=timezone.now() - timezone.timedelta(days=1),
            is_expired=False,
        )
        payload = self._member_payload(
            user__username=user_data.username,
            user__email=user_data.email,
        )
        url = reverse(self.create_with_invite_url_name, args=[invite.key])
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_standard_create_returns_405(self):
        payload = self._member_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_update_member(self):
        member = MemberFactory(organization=self.organization)
        self.client.force_authenticate(member=member)
        payload = {
            'nickname': 'updated_nick',
            'user': {
                'first_name': 'Updated',
                'last_name': 'Name',
            },
        }
        url = self._detail_url(member)
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        member.refresh_from_db()
        self.assertEqual(member.nickname, 'updated_nick')

    def test_delete_member(self):
        member = MemberFactory(organization=self.organization)
        url = self._detail_url(member)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_delete_soft_delete(self):
        member = MemberFactory(organization=self.organization)
        url = self._detail_url(member)
        self.client.delete(url)
        member.refresh_from_db()
        self.assertFalse(member.is_active)

    def test_delete_removes_from_list(self):
        member = MemberFactory(organization=self.organization)
        url = self._detail_url(member)
        self.client.delete(url)
        response = self.client.get(self.list_url)
        for result in response.data['results']:
            self.assertNotEqual(result['id'], member.id)

    def test_update_role(self):
        self.client.force_authenticate(member=self.organization.owner)
        member = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.MEMBER,
        )
        payload = {'role': MemberRoleChoices.MANAGER}
        url = reverse(self.update_role_url_name, args=[member.id])
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['role'], MemberRoleChoices.MANAGER)

    def test_create_duplicate_email_returns_400(self):
        user_data = UserFactory.build()
        MemberFactory.create(
            organization=self.organization,
            user__email=user_data.email,
        )
        invite = InvitationFactory.create(
            organization=self.organization,
            email=user_data.email,
            expired_at=None,
        )
        payload = self._member_payload(
            user__username=user_data.username,
            user__email=user_data.email,
        )
        url = reverse(self.create_with_invite_url_name, args=[invite.key])
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_update_member_with_nonexistent_id(self):
        self.client.force_authenticate(member=self.organization.owner)
        url = self._detail_url(MemberFactory.build(id=99999))
        response = self.client.patch(url, data={'nickname': 'ghost'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_update_member_role_invalid_value(self):
        self.client.force_authenticate(member=self.organization.owner)
        member = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.MEMBER,
        )
        url = reverse(self.update_role_url_name, args=[member.id])
        response = self.client.patch(url, data={'role': 'invalid_role'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_with_invite_accepted(self):
        user_data = UserFactory.build()
        invite = InvitationFactory.create(
            organization=self.organization,
            email=user_data.email,
            expired_at=None,
            is_accepted=True,
        )
        payload = self._member_payload(
            user__username=user_data.username,
            user__email=user_data.email,
        )
        url = reverse(self.create_with_invite_url_name, args=[invite.key])
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data['detail'],
            InvitationErrorMessages.INVITATION_NOT_FOUND.label,
        )

    def test_choices_endpoint(self):
        MemberFactory.create_batch(size=3, organization=self.organization)
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        if response.data['count'] > 0:
            self.assertIn('value', response.data['results'][0])
            self.assertIn('label', response.data['results'][0])
