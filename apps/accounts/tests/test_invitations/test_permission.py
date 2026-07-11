from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import InvitationEmailErrorMessages, MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class InvitationPermissionTestCase(APITestCaseMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.detail_url_name = 'accounts:invitations-detail'
        cls.list_url = reverse('accounts:invitations-list')
        cls.send_email_url_name = 'accounts:invitations-send-email'

    def setUp(self):
        self.organization = self.new_account()

    def _detail_url(self, invitation):
        return reverse(self.detail_url_name, args=[invitation.pk])

    def _send_email_url(self, invitation):
        return reverse(self.send_email_url_name, args=[invitation.pk])

    def _create_invitation(self, **kwargs):
        return InvitationFactory(organization=self.organization, **kwargs)

    def _invitation_payload(self, **overrides):
        data = InvitationFactory.build()
        payload = {
            'email': data.email,
            'role': data.role,
            'expired_at': data.expired_at,
        }
        payload.update(overrides)
        return payload

    # --- Unauthenticated ---

    def test_not_authenticated_list(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_create(self):
        self.client.force_authenticate(user=None)
        payload = self._invitation_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_retrieve(self):
        invitation = self._create_invitation()
        self.client.force_authenticate(user=None)
        url = self._detail_url(invitation)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_update(self):
        invitation = self._create_invitation()
        self.client.force_authenticate(user=None)
        url = self._detail_url(invitation)
        payload = self._invitation_payload(role=MemberRoleChoices.ADMIN)
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_delete(self):
        invitation = self._create_invitation()
        self.client.force_authenticate(user=None)
        url = self._detail_url(invitation)
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_send_email(self):
        invitation = self._create_invitation()
        self.client.force_authenticate(user=None)
        url = self._send_email_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    # --- Inactive member ---

    def _assert_inactive_forbidden(self, method, url, data=None):
        member = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
            is_active=False,
        )
        self.client.force_authenticate(member=member)
        kwargs = {'format': 'json'} if method in ('post', 'put', 'patch') else {}
        if data:
            kwargs['data'] = data
        response = getattr(self.client, method)(url, **kwargs)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_list(self):
        self._assert_inactive_forbidden('get', self.list_url)

    def test_not_active_member_create(self):
        self._assert_inactive_forbidden(
            'post', self.list_url, data=self._invitation_payload()
        )

    def test_not_active_member_retrieve(self):
        invitation = self._create_invitation()
        self._assert_inactive_forbidden('get', self._detail_url(invitation))

    def test_not_active_member_update(self):
        invitation = self._create_invitation()
        self._assert_inactive_forbidden(
            'put',
            self._detail_url(invitation),
            data=self._invitation_payload(role=MemberRoleChoices.ADMIN),
        )

    def test_not_active_member_delete(self):
        invitation = self._create_invitation()
        self._assert_inactive_forbidden('delete', self._detail_url(invitation))

    def test_not_active_member_send_email(self):
        invitation = self._create_invitation()
        self._assert_inactive_forbidden('post', self._send_email_url(invitation))

    # --- Member role (lowest) ---

    def _assert_member_forbidden(self, method, url, data=None):
        member = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.MEMBER,
        )
        self.client.force_authenticate(member=member)
        kwargs = {'format': 'json'} if method in ('post', 'put', 'patch') else {}
        if data:
            kwargs['data'] = data
        response = getattr(self.client, method)(url, **kwargs)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_member_cannot_create(self):
        self._assert_member_forbidden(
            'post', self.list_url, data=self._invitation_payload()
        )

    def test_member_cannot_update(self):
        invitation = self._create_invitation()
        self._assert_member_forbidden(
            'put',
            self._detail_url(invitation),
            data=self._invitation_payload(role=MemberRoleChoices.ADMIN),
        )

    def test_member_cannot_delete(self):
        invitation = self._create_invitation()
        self._assert_member_forbidden('delete', self._detail_url(invitation))

    def test_member_cannot_send_email(self):
        invitation = self._create_invitation()
        self._assert_member_forbidden('post', self._send_email_url(invitation))

    # --- Admin role ---

    def test_admin_can_create_manager_invite(self):
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        payload = self._invitation_payload(role=MemberRoleChoices.MANAGER)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_admin_can_create_member_invite(self):
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        payload = self._invitation_payload(role=MemberRoleChoices.MEMBER)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_admin_cannot_create_admin_invite(self):
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        payload = self._invitation_payload(role=MemberRoleChoices.ADMIN)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_admin_cannot_create_owner_invite(self):
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        payload = self._invitation_payload(role=MemberRoleChoices.OWNER)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_admin_can_retrieve_admin_invite(self):
        invite = self._create_invitation(role=MemberRoleChoices.ADMIN)
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        url = self._detail_url(invite)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_retrieve_manager_invite(self):
        invite = self._create_invitation(role=MemberRoleChoices.MANAGER)
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        url = self._detail_url(invite)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_retrieve_member_invite(self):
        invite = self._create_invitation(role=MemberRoleChoices.MEMBER)
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        url = self._detail_url(invite)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Owner role ---

    def test_owner_can_create_any_role(self):
        payload = self._invitation_payload(role=MemberRoleChoices.OWNER)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_owner_can_retrieve_owner_invite(self):
        invite = self._create_invitation(role=MemberRoleChoices.OWNER)
        url = self._detail_url(invite)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_can_retrieve_admin_invite(self):
        invite = self._create_invitation(role=MemberRoleChoices.ADMIN)
        url = self._detail_url(invite)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Cross-org ---

    def test_cross_org_retrieve_returns_404(self):
        invitation = self._create_invitation()
        other_org = OrganizationFactory.create()
        self.client.force_authenticate(member=other_org.owner)
        url = self._detail_url(invitation)
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_update_returns_404(self):
        invitation = self._create_invitation()
        other_org = OrganizationFactory.create()
        self.client.force_authenticate(member=other_org.owner)
        url = self._detail_url(invitation)
        payload = self._invitation_payload()
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_delete_returns_404(self):
        invitation = self._create_invitation()
        other_org = OrganizationFactory.create()
        self.client.force_authenticate(member=other_org.owner)
        url = self._detail_url(invitation)
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_send_email_returns_404(self):
        invitation = self._create_invitation()
        other_org = OrganizationFactory.create()
        self.client.force_authenticate(member=other_org.owner)
        url = self._send_email_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    # --- Send email edge cases ---

    @override_settings(FRONTEND_URL='http://example.com')
    def test_send_email_cooldown_returns_429(self):
        invitation = self._create_invitation(
            expired_at=timezone.now() + timedelta(days=7),
            last_email_sent_at=timezone.now(),
        )
        url = self._send_email_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(
            response.data['code'],
            InvitationEmailErrorMessages.COOLDOWN_ACTIVE.value,
        )
        self.assertIn('retry_after_seconds', response.data)

    @override_settings(FRONTEND_URL='http://example.com')
    def test_send_email_expired_returns_400(self):
        invitation = self._create_invitation(
            is_expired=True,
            expired_at=timezone.now() - timedelta(days=1),
        )
        url = self._send_email_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    @override_settings(FRONTEND_URL='http://example.com')
    def test_send_email_accepted_returns_400(self):
        invitation = self._create_invitation(
            is_accepted=True,
            expired_at=timezone.now() + timedelta(days=7),
        )
        url = self._send_email_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
