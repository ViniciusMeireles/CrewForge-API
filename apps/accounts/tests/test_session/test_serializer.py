from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin


class SessionSerializerTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.session_url = reverse('accounts:session')

    def test_response_keys_without_org_context(self):
        self.new_account(organization_login=False)
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            set(response.data.keys()),
            {'user', 'organizations', 'organization', 'member'},
        )

    def test_response_keys_with_org_context(self):
        self.new_account(organization_login=True)
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            set(response.data.keys()),
            {'user', 'organizations', 'organization', 'member'},
        )

    def test_user_sub_fields(self):
        self.new_account(organization_login=True)
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        user_data = response.data['user']
        self.assertEqual(
            set(user_data.keys()),
            {'id', 'username', 'email', 'first_name', 'last_name'},
        )

    def test_organization_sub_fields(self):
        self.new_account(organization_login=True)
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        org_data = response.data['organization']
        self.assertEqual(
            set(org_data.keys()),
            {'id', 'name', 'slug', 'profile'},
        )

    def test_member_sub_fields(self):
        self.new_account(organization_login=True)
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        member_data = response.data['member']
        self.assertEqual(
            set(member_data.keys()),
            {'id', 'role', 'nickname', 'permissions', 'last_login_at'},
        )

    def test_permissions_sub_fields(self):
        self.new_account(organization_login=True)
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        permissions = response.data['member']['permissions']
        self.assertEqual(
            set(permissions.keys()),
            {
                'is_owner',
                'is_admin',
                'is_manager',
                'is_member',
                'has_owner_permission',
                'has_admin_permission',
                'has_manager_permission',
                'has_member_permission',
            },
        )

    def test_owner_permissions_are_true(self):
        self.new_account(organization_login=True)
        response = self.client.get(self.session_url)
        permissions = response.data['member']['permissions']
        self.assertTrue(permissions['is_owner'])
        self.assertTrue(permissions['has_owner_permission'])
        self.assertTrue(permissions['has_admin_permission'])
        self.assertTrue(permissions['has_manager_permission'])
        self.assertTrue(permissions['has_member_permission'])

    def test_organization_is_none_without_org_context(self):
        self.new_account(organization_login=False)
        response = self.client.get(self.session_url)
        self.assertIsNone(response.data['organization'])

    def test_member_is_none_without_org_context(self):
        self.new_account(organization_login=False)
        response = self.client.get(self.session_url)
        self.assertIsNone(response.data['member'])
