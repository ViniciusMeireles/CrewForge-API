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

    def test_no_retrieve(self):
        detail_url = reverse('accounts:signup-detail', args=[1])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_no_update(self):
        detail_url = reverse('accounts:signup-detail', args=[1])
        response = self.client.put(detail_url, data={}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_no_partial_update(self):
        detail_url = reverse('accounts:signup-detail', args=[1])
        response = self.client.patch(detail_url, data={}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_no_delete(self):
        detail_url = reverse('accounts:signup-detail', args=[1])
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_405_METHOD_NOT_ALLOWED)
