from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class SessionCRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.session_url = reverse('accounts:session')

    def test_not_authenticated_returns_401(self):
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_no_org_returns_user_and_organizations(self):
        organization = self.new_account(organization_login=False)
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        user_id = organization.owner.user.id
        self.assertEqual(response.data['user']['id'], user_id)
        self.assertIn('organizations', response.data)
        self.assertIsNone(response.data['organization'])
        self.assertIsNone(response.data['member'])

    def test_authenticated_no_org_organizations_list_is_empty(self):
        organization = self.new_account(organization_login=False)
        another_org = OrganizationFactory.create()
        MemberFactory.create(
            user=organization.owner.user,
            organization=another_org,
            is_active=False,
        )
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for org_data in response.data['organizations']:
            self.assertIn(org_data['id'], [organization.id])

    def test_authenticated_with_org_returns_full_response(self):
        organization = self.new_account(organization_login=True)
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        self.assertEqual(response.data['user']['id'], organization.owner.user.id)
        self.assertEqual(response.data['organization']['id'], organization.id)
        self.assertEqual(response.data['member']['id'], organization.owner.id)
        self.assertEqual(response.data['member']['role'], 'owner')
        self.assertEqual(
            response.data['member']['nickname'], organization.owner.nickname
        )

    def test_session_includes_member_permissions(self):
        self.new_account(organization_login=True)
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        permissions = response.data['member']['permissions']
        self.assertIsNotNone(permissions)
        self.assertIn('is_owner', permissions)
        self.assertIn('is_admin', permissions)
        self.assertIn('is_manager', permissions)
        self.assertIn('is_member', permissions)
        self.assertIn('has_owner_permission', permissions)
        self.assertIn('has_admin_permission', permissions)
        self.assertIn('has_manager_permission', permissions)
        self.assertIn('has_member_permission', permissions)
        self.assertTrue(permissions['is_owner'])
        self.assertTrue(permissions['has_owner_permission'])

    def test_session_includes_last_login_at(self):
        self.new_account(organization_login=True)
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        self.assertIsNotNone(response.data['member']['last_login_at'])

    def test_organizations_list_only_active_memberships(self):
        organization = self.new_account(organization_login=True)
        owner_user = organization.owner.user

        other_org = OrganizationFactory.create()
        MemberFactory.create(
            user=owner_user,
            organization=other_org,
            is_active=False,
        )

        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        org_ids = [org['id'] for org in response.data['organizations']]
        self.assertIn(organization.id, org_ids)
        self.assertNotIn(other_org.id, org_ids)

    def test_inactive_member_returns_no_org_context(self):
        organization = self.new_account(organization_login=True)
        organization.owner.is_active = False
        organization.owner.save()

        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsNotNone(response.data['user'])
        self.assertIsNone(response.data['organization'])
        self.assertIsNone(response.data['member'])
