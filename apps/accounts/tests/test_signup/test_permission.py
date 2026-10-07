from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory


class SignupPermissionTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse('accounts:signup-list')

    def _valid_payload(self):
        user_data = UserFactory.build()
        org_data = OrganizationFactory.build()
        member_data = MemberFactory.build()
        return {
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

    def test_not_authenticated_can_signup(self):
        payload = self._valid_payload()
        response = self.client.post(self.url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_not_authenticated_can_create_new_account(self):
        response = self.client.post(self.url, data=self._valid_payload(), format='json')
        self.assertNotEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_no_list(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, http_status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_no_detail_route(self):
        detail_url = f'{self.url}1/'
        for method in ['get', 'put', 'patch', 'delete']:
            with self.subTest(method=method):
                response = getattr(self.client, method)(detail_url)
                self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
