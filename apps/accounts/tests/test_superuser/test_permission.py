from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class SuperuserMemberPermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account(login=False)
        user = UserFactory(is_superuser=True, is_staff=True)
        self.superuser_member = MemberFactory(
            organization=self.organization,
            user=user,
            role=MemberRoleChoices.MEMBER,
        )
        self.client.force_authenticate(member=self.superuser_member)

    def test_cannot_update_the_organization(self):
        url = reverse('accounts:organizations-detail', args=[self.organization.id])
        response = self.client.patch(url, data={'name': 'Renamed'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_cannot_change_a_member_role(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        url = reverse('accounts:members-detail', args=[member.id])
        response = self.client.patch(url, data={'role': 'admin'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_cannot_create_an_invitation(self):
        data = InvitationFactory.build()
        payload = {
            'email': data.email,
            'role': data.role,
            'expired_at': data.expired_at,
        }
        response = self.client.post(
            reverse('accounts:invitations-list'), data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_cannot_read_the_audit_trail(self):
        response = self.client.get(reverse('audit:audit_events-list'))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
