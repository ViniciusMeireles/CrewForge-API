from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory

User = get_user_model()


class SignupCRUDTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse('accounts:signup-list')

    def test_create_account(self):
        user_data = UserFactory.build()
        organization_data = OrganizationFactory.build()
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
                'name': organization_data.name,
                'slug': organization_data.slug,
            },
            'nickname': member_data.nickname,
        }

        response = self.client.post(path=self.url, data=payload, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('user').get('username'), user_data.username)
        self.assertEqual(response.data.get('user').get('email'), user_data.email)
        self.assertEqual(
            response.data.get('user').get('first_name'), user_data.first_name
        )
        self.assertEqual(
            response.data.get('user').get('last_name'), user_data.last_name
        )
        self.assertEqual(
            response.data.get('organization').get('name'), organization_data.name
        )
        self.assertEqual(
            response.data.get('organization').get('slug'), organization_data.slug
        )
        self.assertEqual(response.data.get('nickname'), member_data.nickname)
        self.assertEqual(response.data.get('role'), MemberRoleChoices.OWNER)
        self.assertIsNotNone(response.data['user']['auth_token']['access'])
        self.assertIsNotNone(response.data['user']['auth_token']['refresh'])

        user = User.objects.get_or_none(
            **{User.USERNAME_FIELD: getattr(user_data, User.USERNAME_FIELD)}
        )
        self.assertIsNotNone(user)
        self.assertIsNotNone(user.password)

    def test_create_account_existing_user(self):
        existing_user = OrganizationFactory.create().owner.user
        organization_data = OrganizationFactory.build()
        member_data = MemberFactory.build()

        payload = {
            'user': {
                'username': existing_user.username,
                'email': existing_user.email,
                'first_name': existing_user.first_name,
                'last_name': existing_user.last_name,
                'password': 'passWord*123',
            },
            'organization': {
                'name': organization_data.name,
                'slug': organization_data.slug,
            },
            'nickname': member_data.nickname,
        }

        response = self.client.post(path=self.url, data=payload, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_account_empty_password(self):
        user_data = UserFactory.build()
        organization_data = OrganizationFactory.build()
        member_data = MemberFactory.build()

        payload = {
            'user': {
                'username': user_data.username,
                'email': user_data.email,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name,
                'password': '',
            },
            'organization': {
                'name': organization_data.name,
                'slug': organization_data.slug,
            },
            'nickname': member_data.nickname,
        }

        response = self.client.post(path=self.url, data=payload, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('user', response.data['error']['details'])
