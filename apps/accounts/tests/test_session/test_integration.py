from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory

User = get_user_model()


class SessionIntegrationTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.signup_url = reverse('accounts:signup-list')
        cls.session_url = reverse('accounts:session')
        cls.logout_url = reverse('accounts:logout')

    def test_full_session_flow(self):
        user_data = UserFactory.build()
        org_data = OrganizationFactory.build()
        member_data = MemberFactory.build()

        payload = {
            'user': {
                'username': user_data.username,
                'email': user_data.email,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name,
                'password': user_data.password,
            },
            'organization': {
                'name': org_data.name,
                'slug': org_data.slug,
            },
            'nickname': member_data.nickname,
        }

        signup_resp = self.client.post(self.signup_url, data=payload, format='json')
        self.assertEqual(signup_resp.status_code, http_status.HTTP_201_CREATED)
        access_token = signup_resp.data['user']['auth_token']['access']
        refresh_token = signup_resp.data['user']['auth_token']['refresh']
        org_id = signup_resp.data['organization']['id']
        member_id = signup_resp.data['id']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsNotNone(response.data['user'])
        self.assertEqual(response.data['user']['id'], signup_resp.data['user']['id'])
        self.assertIsNotNone(response.data['organizations'])
        self.assertIsNone(response.data['organization'])
        self.assertIsNone(response.data['member'])

        org_login_url = reverse('accounts:organizations-login', args=[org_id])
        self.client.post(org_login_url, format='json')

        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsNotNone(response.data['organization'])
        self.assertEqual(response.data['organization']['id'], org_id)
        self.assertIsNotNone(response.data['member'])
        self.assertEqual(response.data['member']['id'], member_id)
        self.assertTrue(response.data['member']['permissions']['is_owner'])

        logout_resp = self.client.post(
            self.logout_url,
            data={'refresh': refresh_token},
            format='json',
        )
        self.assertEqual(logout_resp.status_code, http_status.HTTP_204_NO_CONTENT)

        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsNotNone(response.data['user'])
        self.assertIsNotNone(response.data['organizations'])
        self.assertIsNone(response.data['organization'])
        self.assertIsNone(response.data['member'])

        self.client.credentials()
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
