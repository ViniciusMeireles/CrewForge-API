from datetime import timedelta

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class InvitationIntegrationTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:invitations-list')

    def _detail_url(self, invitation):
        return reverse('accounts:invitations-detail', args=[invitation.pk])

    def _send_email_url(self, invitation):
        return reverse('accounts:invitations-send-email', args=[invitation.pk])

    def test_full_crud_flow(self):
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': MemberRoleChoices.ADMIN,
            'expired_at': invitation_data.expired_at,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        invite_id = response.data['id']

        list_resp = self.client.get(self.list_url)
        self.assertEqual(list_resp.status_code, http_status.HTTP_200_OK)
        self.assertGreater(list_resp.data['count'], 0)

        detail_url = reverse('accounts:invitations-detail', args=[invite_id])
        retrieve_resp = self.client.get(detail_url)
        self.assertEqual(retrieve_resp.status_code, http_status.HTTP_200_OK)

        update_payload = {
            'email': f'updated.{invitation_data.email}',
            'role': MemberRoleChoices.MEMBER,
            'expired_at': invitation_data.expired_at,
        }
        update_resp = self.client.put(detail_url, data=update_payload, format='json')
        self.assertEqual(update_resp.status_code, http_status.HTTP_200_OK)

        delete_resp = self.client.delete(detail_url, format='json')
        self.assertEqual(delete_resp.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_create_then_send_email(self):
        invitation_data = InvitationFactory.build()
        payload = {
            'email': invitation_data.email,
            'role': MemberRoleChoices.MEMBER,
            'expired_at': timezone.now() + timedelta(days=7),
        }
        with override_settings(FRONTEND_URL='http://example.com'):
            create_resp = self.client.post(self.list_url, data=payload, format='json')
            self.assertEqual(create_resp.status_code, http_status.HTTP_201_CREATED)
            self.assertEqual(len(mail.outbox), 0)

            invite_id = create_resp.data['id']
            send_url = reverse('accounts:invitations-send-email', args=[invite_id])
            send_resp = self.client.post(send_url, format='json')
            self.assertEqual(send_resp.status_code, http_status.HTTP_200_OK)
            self.assertEqual(len(mail.outbox), 1)

    def test_role_scoped_list_for_admin(self):
        InvitationFactory.create(
            organization=self.organization, role=MemberRoleChoices.OWNER
        )
        InvitationFactory.create(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        InvitationFactory.create(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )

        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertIn(
                result['role'],
                [
                    MemberRoleChoices.ADMIN,
                    MemberRoleChoices.MANAGER,
                    MemberRoleChoices.MEMBER,
                ],
            )

    def test_role_scoped_list_for_owner_sees_all(self):
        InvitationFactory.create(
            organization=self.organization, role=MemberRoleChoices.OWNER
        )
        InvitationFactory.create(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        InvitationFactory.create(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        InvitationFactory.create(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        roles = {r['role'] for r in response.data['results']}
        self.assertEqual(
            roles,
            {
                MemberRoleChoices.OWNER,
                MemberRoleChoices.ADMIN,
                MemberRoleChoices.MANAGER,
                MemberRoleChoices.MEMBER,
            },
        )

    def test_cross_org_invitation_not_visible(self):
        invitation = InvitationFactory.create(organization=self.organization)
        other_org = OrganizationFactory.create()
        self.client.force_authenticate(member=other_org.owner)

        detail_url = self._detail_url(invitation)
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
