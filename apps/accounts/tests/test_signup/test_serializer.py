from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory

User = get_user_model()


class SignupSerializerTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse('accounts:signup-list')

    def test_create_returns_expected_fields(self):
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

        response = self.client.post(self.url, data=payload, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(
            set(response.data.keys()),
            {
                'id',
                'user',
                'organization',
                'nickname',
                'is_active',
                'role',
                'created_at',
                'updated_at',
                'created_by',
                'updated_by',
                'last_login_at',
                'access',
                'refresh',
            },
        )

    def test_create_user_serializer_fields(self):
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

        response = self.client.post(self.url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

        user_fields = set(response.data['user'].keys())
        expected_user_fields = {
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'auth_token',
        }
        self.assertEqual(user_fields, expected_user_fields)

    def test_create_token_in_nested_auth_token(self):
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

        response = self.client.post(self.url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        auth_token = response.data['user']['auth_token']
        self.assertIn('access', auth_token)
        self.assertIn('refresh', auth_token)
        self.assertIsNotNone(auth_token['access'])
        self.assertIsNotNone(auth_token['refresh'])

    def test_create_auto_populates_owner_role(self):
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

        response = self.client.post(self.url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], MemberRoleChoices.OWNER)

    def test_validate_duplicate_username(self):
        existing_user = OrganizationFactory.create().owner.user
        org_data = OrganizationFactory.build()
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
                'name': org_data.name,
                'slug': org_data.slug,
            },
            'nickname': member_data.nickname,
        }

        response = self.client.post(self.url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_validate_empty_password(self):
        user_data = UserFactory.build()
        org_data = OrganizationFactory.build()
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
                'name': org_data.name,
                'slug': org_data.slug,
            },
            'nickname': member_data.nickname,
        }

        response = self.client.post(self.url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', str(response.data))

    def test_create_creates_user_in_database(self):
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

        response = self.client.post(self.url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

        user = User.objects.get_or_none(
            **{User.USERNAME_FIELD: getattr(user_data, User.USERNAME_FIELD)}
        )
        self.assertIsNotNone(user)
        self.assertIsNotNone(user.password)
        self.assertNotEqual(user.password, user_data.password)
