from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class InvitationSerializerTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:invitations-list')

    def _create_invitation(self, **kwargs):
        return InvitationFactory(organization=self.organization, **kwargs)

    def test_list_serializer_fields(self):
        self._create_invitation()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        result = response.data['results'][0]
        expected_fields = {
            'id',
            'email',
            'is_expired',
            'is_accepted',
            'expired_at',
            'role',
            'organization',
            'last_email_sent_at',
        }
        self.assertEqual(set(result.keys()), expected_fields)

    def test_detail_serializer_fields(self):
        invitation = self._create_invitation()
        url = reverse('accounts:invitations-detail', args=[invitation.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        expected_fields = {
            'id',
            'email',
            'is_expired',
            'is_accepted',
            'expired_at',
            'role',
            'organization',
            'last_email_sent_at',
        }
        self.assertEqual(set(response.data.keys()), expected_fields)

    def test_send_email_not_in_read_only_fields(self):
        payload = {
            'email': 'new@example.com',
            'role': MemberRoleChoices.MEMBER,
            'expired_at': timezone.now() + timedelta(days=7),
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertNotIn('send_email', response.data)

    def test_id_read_only_on_create(self):
        payload = {
            'id': 9999,
            'email': 'new@example.com',
            'role': MemberRoleChoices.MEMBER,
            'expired_at': timezone.now() + timedelta(days=7),
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertNotEqual(response.data['id'], 9999)

    def test_organization_read_only_on_create(self):
        payload = {
            'email': 'new@example.com',
            'role': MemberRoleChoices.MEMBER,
            'expired_at': timezone.now() + timedelta(days=7),
            'organization': 0,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['organization'], self.organization.id)

    def test_last_email_sent_at_read_only_on_create(self):
        payload = {
            'email': 'new@example.com',
            'role': MemberRoleChoices.MEMBER,
            'expired_at': timezone.now() + timedelta(days=7),
            'last_email_sent_at': timezone.now(),
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertIsNone(response.data.get('last_email_sent_at'))

    def test_is_accepted_read_only_on_create(self):
        payload = {
            'email': 'new@example.com',
            'role': MemberRoleChoices.MEMBER,
            'expired_at': timezone.now() + timedelta(days=7),
            'is_accepted': True,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertFalse(response.data['is_accepted'])

    def test_validate_email_duplicate_returns_400(self):
        invitation = self._create_invitation(
            expired_at=timezone.now() + timedelta(days=7),
            is_expired=False,
            is_accepted=False,
        )
        payload = {
            'email': invitation.email,
            'role': MemberRoleChoices.MEMBER,
            'expired_at': timezone.now() + timedelta(days=7),
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_validate_email_duplicate_allows_expired(self):
        invitation = self._create_invitation(
            is_expired=True,
            expired_at=timezone.now() - timedelta(days=1),
        )
        payload = {
            'email': invitation.email,
            'role': MemberRoleChoices.MEMBER,
            'expired_at': timezone.now() + timedelta(days=7),
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_validate_email_duplicate_allows_accepted(self):
        invitation = self._create_invitation(is_accepted=True)
        payload = {
            'email': invitation.email,
            'role': MemberRoleChoices.MEMBER,
            'expired_at': timezone.now() + timedelta(days=7),
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_validate_email_allows_update_same_email(self):
        invitation = self._create_invitation(
            expired_at=timezone.now() + timedelta(days=7),
        )
        url = reverse('accounts:invitations-detail', args=[invitation.pk])
        payload = {
            'email': invitation.email,
            'role': MemberRoleChoices.ADMIN,
            'expired_at': invitation.expired_at,
        }
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_validate_role_owner_requires_owner_permission(self):
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        payload = {
            'email': 'new@example.com',
            'role': MemberRoleChoices.OWNER,
            'expired_at': timezone.now() + timedelta(days=7),
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_validate_role_admin_requires_owner_permission(self):
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        payload = {
            'email': 'new@example.com',
            'role': MemberRoleChoices.ADMIN,
            'expired_at': timezone.now() + timedelta(days=7),
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_validate_role_member_requires_admin_permission(self):
        member = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.MEMBER,
        )
        self.client.force_authenticate(member=member)
        payload = {
            'email': 'new@example.com',
            'role': MemberRoleChoices.MEMBER,
            'expired_at': timezone.now() + timedelta(days=7),
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_owner_can_set_any_role(self):
        for role in [
            MemberRoleChoices.OWNER,
            MemberRoleChoices.ADMIN,
            MemberRoleChoices.MANAGER,
            MemberRoleChoices.MEMBER,
        ]:
            payload = {
                'email': f'new.{role}@example.com',
                'role': role,
                'expired_at': timezone.now() + timedelta(days=7),
            }
            response = self.client.post(self.list_url, data=payload, format='json')
            self.assertEqual(
                response.status_code,
                http_status.HTTP_201_CREATED,
                f'Owner should be able to set role={role}',
            )

    def test_admin_can_set_manager_and_member(self):
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        for role in [MemberRoleChoices.MANAGER, MemberRoleChoices.MEMBER]:
            payload = {
                'email': f'new.{role}@example.com',
                'role': role,
                'expired_at': timezone.now() + timedelta(days=7),
            }
            response = self.client.post(self.list_url, data=payload, format='json')
            self.assertEqual(
                response.status_code,
                http_status.HTTP_201_CREATED,
                f'Admin should be able to set role={role}',
            )
