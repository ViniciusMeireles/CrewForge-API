from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory

User = get_user_model()


class SignupIntegrationTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.signup_url = reverse('accounts:signup-list')
        cls.token_url = reverse('accounts:token_obtain_pair')
        cls.org_list_url = reverse('accounts:organizations-list')

    def test_full_signup_flow(self):
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
        self.assertIsNotNone(access_token)

        token_resp = self.client.post(
            self.token_url,
            data={
                'username': user_data.username,
                'password': user_data.password,
            },
            format='json',
        )
        self.assertEqual(token_resp.status_code, http_status.HTTP_200_OK)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        org_list_resp = self.client.get(self.org_list_url)
        self.assertEqual(org_list_resp.status_code, http_status.HTTP_200_OK)
        self.assertGreaterEqual(org_list_resp.data['count'], 1)
