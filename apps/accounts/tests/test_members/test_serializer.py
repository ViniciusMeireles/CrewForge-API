from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class MemberModelSerializerTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:members-list')

    def test_list_serializer_fields(self):
        MemberFactory(organization=self.organization)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        result = response.data['results'][0]
        expected_fields = {
            'id',
            'user',
            'nickname',
            'role',
            'organization',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
            'last_login_at',
        }
        self.assertEqual(set(result.keys()), expected_fields)

    def test_detail_serializer_fields(self):
        member = MemberFactory(organization=self.organization)
        url = reverse('accounts:members-detail', args=[member.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        expected_fields = {
            'id',
            'user',
            'nickname',
            'role',
            'organization',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
            'last_login_at',
        }
        self.assertEqual(set(response.data.keys()), expected_fields)

    def test_user_nested_fields_in_list(self):
        member = MemberFactory(organization=self.organization)
        response = self.client.get(reverse('accounts:members-detail', args=[member.id]))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        user_data = response.data['user']
        self.assertIn('id', user_data)
        self.assertIn('username', user_data)
        self.assertIn('email', user_data)
        self.assertIn('first_name', user_data)
        self.assertIn('last_name', user_data)

    def test_read_only_fields_ignored_on_create(self):
        url = reverse(
            'accounts:members-create-with-invite',
            args=['00000000-0000-0000-0000-000000000000'],
        )
        payload = {
            'id': 9999,
            'is_active': False,
            'role': MemberRoleChoices.OWNER,
            'user': {
                'username': 'testuser',
                'first_name': 'Test',
                'last_name': 'User',
            },
        }
        response = self.client.post(url, data=payload, format='json')
        self.assertNotEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_validate_duplicate_email_in_org(self):
        existing = MemberFactory(organization=self.organization)
        existing.user.email = 'dupe@example.com'
        existing.user.save()
        user_data = UserFactory.build(email='dupe@example.com')
        invite = InvitationFactory.create(
            organization=self.organization,
            email=user_data.email,
            expired_at=None,
        )
        payload = {
            'user': {
                'username': user_data.username,
                'email': user_data.email,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name,
                'password': user_data.password,
            },
            'nickname': 'dupe_member',
        }
        url = reverse('accounts:members-create-with-invite', args=[invite.key])
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_read_only_fields_on_create(self):
        user_data = UserFactory.build()
        invite = InvitationFactory.create(
            organization=self.organization,
            email=user_data.email,
            expired_at=None,
        )
        payload = {
            'user': {
                'username': user_data.username,
                'email': user_data.email,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name,
                'password': user_data.password,
            },
            'nickname': 'readonly_test',
            'role': MemberRoleChoices.OWNER,
        }
        url = reverse('accounts:members-create-with-invite', args=[invite.key])
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertNotEqual(response.data['role'], MemberRoleChoices.OWNER)
        self.assertEqual(response.data['role'], MemberRoleChoices.MEMBER)

    def test_create_read_only_fields_ignored(self):
        user_data = UserFactory.build()
        invite = InvitationFactory.create(
            organization=self.organization,
            email=user_data.email,
            expired_at=None,
        )
        payload = {
            'id': 99999,
            'is_active': False,
            'user': {
                'username': user_data.username,
                'email': user_data.email,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name,
                'password': user_data.password,
            },
            'nickname': 'ignore_test',
        }
        url = reverse('accounts:members-create-with-invite', args=[invite.key])
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertNotEqual(response.data['id'], 99999)
        self.assertTrue(response.data['is_active'])

    def test_update_read_only_fields_ignored(self):
        member = MemberFactory(organization=self.organization)
        original_created_by = member.created_by_id
        self.client.force_authenticate(member=self.organization.owner)
        url = reverse('accounts:members-detail', args=[member.id])
        payload = {
            'nickname': 'ignore_ro',
            'created_by': None,
            'updated_by': None,
        }
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        member.refresh_from_db()
        self.assertEqual(member.created_by_id, original_created_by)
        self.assertEqual(member.nickname, 'ignore_ro')


class MemberWithInviteCreateSerializerTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()

    def test_create_with_invite_returns_auth_token(self):
        user_data = UserFactory.build()
        invite = InvitationFactory.create(
            organization=self.organization,
            email=user_data.email,
            expired_at=None,
        )
        payload = {
            'user': {
                'username': user_data.username,
                'email': user_data.email,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name,
                'password': user_data.password,
            },
            'nickname': 'testnick',
        }
        url = reverse('accounts:members-create-with-invite', args=[invite.key])
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertIn('auth_token', response.data['user'])
        self.assertIn('access', response.data['user']['auth_token'])
        self.assertIn('refresh', response.data['user']['auth_token'])
        self.assertIsNotNone(response.data['user']['auth_token']['access'])
        self.assertIsNotNone(response.data['user']['auth_token']['refresh'])

    def test_create_with_invite_role_from_invitation(self):
        user_data = UserFactory.build()
        invite = InvitationFactory.create(
            organization=self.organization,
            email=user_data.email,
            role=MemberRoleChoices.MANAGER,
            expired_at=None,
        )
        payload = {
            'user': {
                'username': user_data.username,
                'email': user_data.email,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name,
                'password': user_data.password,
            },
            'nickname': 'testnick',
            'role': MemberRoleChoices.OWNER,
        }
        url = reverse('accounts:members-create-with-invite', args=[invite.key])
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], MemberRoleChoices.MANAGER)

    def test_create_with_invite_ignores_role_in_payload(self):
        user_data = UserFactory.build()
        member_data = MemberFactory.build()
        invite = InvitationFactory.create(
            organization=self.organization,
            email=user_data.email,
            role=MemberRoleChoices.MANAGER,
            expired_at=None,
        )
        payload = {
            'user': {
                'username': user_data.username,
                'email': user_data.email,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name,
                'password': user_data.password,
            },
            'nickname': member_data.nickname,
        }
        url = reverse('accounts:members-create-with-invite', args=[invite.key])
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], MemberRoleChoices.MANAGER)


class MemberUpdateSerializerTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()

    def test_role_is_read_only_on_update(self):
        member = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.MEMBER,
        )
        self.client.force_authenticate(member=self.organization.owner)
        url = reverse('accounts:members-detail', args=[member.id])
        payload = {
            'nickname': 'newnick',
            'role': MemberRoleChoices.ADMIN,
        }
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        member.refresh_from_db()
        self.assertNotEqual(member.role, MemberRoleChoices.ADMIN)


class MemberRoleUpdateSerializerTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.update_role_url_name = 'accounts:members-update-role'

    def _update_role_url(self, member):
        return reverse(self.update_role_url_name, args=[member.id])

    def _create_target(self, role=MemberRoleChoices.MEMBER):
        return MemberFactory.create(
            organization=self.organization,
            role=role,
        )

    def test_update_role(self):
        self.client.force_authenticate(member=self.organization.owner)
        member_to_update = self._create_target()
        payload = {'role': MemberRoleChoices.MANAGER}
        url = self._update_role_url(member_to_update)
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['role'], MemberRoleChoices.MANAGER)

    def test_update_role_validates_owner_only_by_owner(self):
        admin = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        member_to_update = self._create_target()
        payload = {'role': MemberRoleChoices.OWNER}
        url = self._update_role_url(member_to_update)
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    # --- Owner can set any role ---

    def test_owner_can_set_owner_role(self):
        target = self._create_target()
        payload = {'role': MemberRoleChoices.OWNER}
        response = self.client.patch(
            self._update_role_url(target), data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_can_set_admin_role(self):
        target = self._create_target()
        payload = {'role': MemberRoleChoices.ADMIN}
        response = self.client.patch(
            self._update_role_url(target), data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_can_set_manager_role(self):
        target = self._create_target()
        payload = {'role': MemberRoleChoices.MANAGER}
        response = self.client.patch(
            self._update_role_url(target), data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_can_set_member_role(self):
        target = self._create_target(role=MemberRoleChoices.MANAGER)
        payload = {'role': MemberRoleChoices.MEMBER}
        response = self.client.patch(
            self._update_role_url(target), data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Admin role validation ---

    def test_admin_can_set_manager_role(self):
        admin = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        target = self._create_target()
        payload = {'role': MemberRoleChoices.MANAGER}
        response = self.client.patch(
            self._update_role_url(target), data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_set_member_role(self):
        admin = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        target = self._create_target(role=MemberRoleChoices.MANAGER)
        payload = {'role': MemberRoleChoices.MEMBER}
        response = self.client.patch(
            self._update_role_url(target), data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_cannot_set_admin_role(self):
        admin = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        target = self._create_target()
        payload = {'role': MemberRoleChoices.ADMIN}
        response = self.client.patch(
            self._update_role_url(target), data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    # --- Member cannot set any role ---

    def test_member_cannot_set_any_role(self):
        member_role = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.MEMBER,
        )
        self.client.force_authenticate(member=member_role)
        target = self._create_target()
        payload = {'role': MemberRoleChoices.MANAGER}
        response = self.client.patch(
            self._update_role_url(target), data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- Manager cannot set admin ---

    def test_validate_role_hierarchy_manager_cannot_set_admin(self):
        manager = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.MANAGER,
        )
        self.client.force_authenticate(member=manager)
        target = self._create_target()
        payload = {'role': MemberRoleChoices.ADMIN}
        response = self.client.patch(
            self._update_role_url(target), data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- Invalid role value ---

    def test_validate_invalid_role_update(self):
        target = self._create_target()
        payload = {'role': 'invalid_role'}
        response = self.client.patch(
            self._update_role_url(target), data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    # --- Cannot change own role ---

    def test_cannot_change_own_role(self):
        target = self._create_target()
        self.client.force_authenticate(member=target)
        payload = {'role': MemberRoleChoices.ADMIN}
        response = self.client.patch(
            self._update_role_url(target), data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
