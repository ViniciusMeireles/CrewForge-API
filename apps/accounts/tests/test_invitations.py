import datetime

from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.models.invitation import Invitation
from apps.accounts.tests.mixins import APITestCaseMixin


class InvitationAPITestCase(APITestCaseMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.detail_url_name = 'accounts:invitations-detail'
        cls.list_url_name = 'accounts:invitations-list'
        cls.list_url = reverse(cls.list_url_name)
        cls.choices_url = reverse(viewname='accounts:invitations-choices')

    def setUp(self):
        self.organization = self.new_account()

    def test_list_and_choices_invitations(self):
        """Test the list and choices views of the invitations."""
        InvitationFactory.create_batch(size=5, organization=self.organization)

        for url in [self.list_url, self.choices_url]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, http_status.HTTP_200_OK)
            self.assertEqual(response.data.get('count'), 5)

    def test_create_invitation(self):
        """Test the create view of the invitations."""

        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': invitation_data.role,
            'expired_at': invitation_data.expired_at,
        }

        response = self.client.post(
            path=self.list_url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('email'), invitation_data.email)
        self.assertEqual(response.data.get('role'), invitation_data.role)
        self.assertEqual(
            response.data.get('expired_at'),
            invitation_data.expired_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        )
        self.assertEqual(response.data.get('organization'), self.organization.id)
        self.assertEqual(response.data.get('is_expired'), False)

    def test_retrieve_invitation(self):
        """Test the retrieve view of the invitations."""
        invitation = InvitationFactory.create(organization=self.organization)

        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data.get('email'), invitation.email)
        self.assertEqual(response.data.get('role'), invitation.role)
        self.assertEqual(
            response.data.get('expired_at'),
            invitation.expired_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        )
        self.assertEqual(response.data.get('is_expired'), False)
        self.assertEqual(response.data.get('organization'), self.organization.id)

    def test_update_invitation(self):
        """Test the update view of the invitations."""
        invitation = InvitationFactory.create(organization=self.organization)

        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': MemberRoleChoices.ADMIN,
            'expired_at': invitation_data.expired_at,
            'organization': self.organization.id,
        }
        response = self.client.put(
            path=url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data.get('email'), invitation_data.email)
        self.assertEqual(response.data.get('role'), MemberRoleChoices.ADMIN)
        self.assertEqual(
            response.data.get('expired_at'),
            invitation_data.expired_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        )

    def test_delete_invitation(self):
        """Test the delete view of the invitations."""
        invitation = InvitationFactory.create(organization=self.organization)

        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        response = self.client.delete(
            path=url,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            Invitation.objects.filter_actives().filter(id=invitation.id).exists(), False
        )

    def test_not_permission_invitation_create(self):
        member = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.MEMBER,
        )
        self.client.force_authenticate(member=member)

        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': invitation_data.role,
            'expired_at': invitation_data.expired_at,
        }
        response = self.client.post(
            path=self.list_url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_permission_invitation_update(self):
        member = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.MEMBER,
        )
        self.client.force_authenticate(member=member)
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': invitation_data.role,
            'expired_at': invitation_data.expired_at,
        }
        invitation = InvitationFactory.create(organization=self.organization)
        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        response = self.client.put(
            path=url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_permission_invitation_delete(self):
        member = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.MEMBER,
        )
        self.client.force_authenticate(member=member)

        invitation = InvitationFactory.create(organization=self.organization)
        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        response = self.client.delete(
            path=url,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_permission_invitation_access_other_organization(self):
        member = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.MEMBER,
        )
        self.client.force_authenticate(member=member)
        invitation = InvitationFactory.create(organization=self.organization)
        organization2 = OrganizationFactory.create()
        self.client.force_authenticate(member=organization2.owner)
        response = self.client.get(
            self.detail_url_name,
            kwargs={'key': invitation.key},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_expired_invitation(self):
        """Test the expired invitations."""
        invitation = InvitationFactory.create(
            organization=self.organization,
            is_expired=True,
            expired_at=timezone.now() - datetime.timedelta(days=1),
        )

        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data.get('is_expired'), True)
        self.assertEqual(
            response.data.get('expired_at'),
            invitation.expired_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        )

    def test_accepted_invitation(self):
        """Test the accepted invitations."""
        invitation = InvitationFactory.create(
            organization=self.organization,
            is_accepted=True,
        )

        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data.get('is_accepted'), True)

    def test_duplicate_invitation(self):
        """Test the duplicate invitations."""
        invitation = InvitationFactory.create(
            organization=self.organization,
            expired_at=timezone.now() + datetime.timedelta(days=1),
            is_expired=False,
            is_accepted=False,
        )
        response = self.client.post(
            path=self.list_url,
            data={
                'email': invitation.email,
                'role': invitation.role,
                'expired_at': invitation.expired_at,
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_not_authenticated_list_invitations(self):
        """Test the list view of the invitations without authentication."""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_create_invitation(self):
        """Test the create view of the invitations without authentication."""
        self.client.force_authenticate(user=None)
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': invitation_data.role,
            'expired_at': invitation_data.expired_at,
        }
        response = self.client.post(
            path=self.list_url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_retrieve_invitation(self):
        """Test the retrieve view of the invitations without authentication."""
        invitation = InvitationFactory.create(organization=self.organization)
        self.client.force_authenticate(user=None)
        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_update_invitation(self):
        """Test the update view of the invitations without authentication."""
        invitation = InvitationFactory.create(organization=self.organization)
        self.client.force_authenticate(user=None)
        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': MemberRoleChoices.ADMIN,
            'expired_at': invitation_data.expired_at,
            'organization': self.organization.id,
        }
        response = self.client.put(
            path=url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_delete_invitation(self):
        """Test the delete view of the invitations without authentication."""
        invitation = InvitationFactory.create(organization=self.organization)
        self.client.force_authenticate(user=None)
        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        response = self.client.delete(
            path=url,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_active_member_invitation_list(self):
        """Test the list view of the invitations with not active member."""
        member = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
            is_active=False,
        )
        self.client.force_authenticate(member=member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_invitation_create(self):
        """Test the create view of the invitations with not active member."""
        member = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
            is_active=False,
        )
        self.client.force_authenticate(member=member)
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': invitation_data.role,
            'expired_at': invitation_data.expired_at,
        }
        response = self.client.post(
            path=self.list_url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_invitation_retrieve(self):
        """Test the retrieve view of the invitations with not active member."""
        member = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
            is_active=False,
        )
        self.client.force_authenticate(member=member)
        invitation = InvitationFactory.create(organization=self.organization)
        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_invitation_update(self):
        """Test the update view of the invitations with not active member."""
        member = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
            is_active=False,
        )
        self.client.force_authenticate(member=member)
        invitation = InvitationFactory.create(organization=self.organization)
        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': MemberRoleChoices.ADMIN,
            'expired_at': invitation_data.expired_at,
            'organization': self.organization.id,
        }
        response = self.client.put(
            path=url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_invitation_delete(self):
        """Test the delete view of the invitations with not active member."""
        member = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
            is_active=False,
        )
        self.client.force_authenticate(member=member)
        invitation = InvitationFactory.create(organization=self.organization)
        url = reverse(
            self.detail_url_name,
            kwargs={'key': invitation.key},
        )
        response = self.client.delete(
            path=url,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
