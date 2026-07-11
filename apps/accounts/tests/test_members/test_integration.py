from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class MemberIntegrationTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:members-list')
        self.create_with_invite_url_name = 'accounts:members-create-with-invite'
        self.update_role_url_name = 'accounts:members-update-role'

    def _detail_url(self, member):
        return reverse('accounts:members-detail', args=[member.id])

    def test_full_crud_flow_owner(self):
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
            'nickname': 'new_member',
        }
        create_url = reverse(self.create_with_invite_url_name, args=[invite.key])
        create_resp = self.client.post(create_url, data=payload, format='json')
        self.assertEqual(create_resp.status_code, http_status.HTTP_201_CREATED)
        member_id = create_resp.data['id']
        self.assertEqual(create_resp.data['role'], MemberRoleChoices.MANAGER)

        list_resp = self.client.get(self.list_url)
        self.assertEqual(list_resp.status_code, http_status.HTTP_200_OK)
        self.assertGreaterEqual(list_resp.data['count'], 2)

        detail_url = self._detail_url(MemberFactory._meta.model(id=member_id))
        retrieve_resp = self.client.get(detail_url)
        self.assertEqual(retrieve_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(retrieve_resp.data['id'], member_id)

        self.client.force_authenticate(member=self.organization.owner)
        patch_resp = self.client.patch(
            detail_url, data={'nickname': 'updated_nick'}, format='json'
        )
        self.assertEqual(patch_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(patch_resp.data['nickname'], 'updated_nick')

        delete_resp = self.client.delete(detail_url)
        self.assertEqual(delete_resp.status_code, http_status.HTTP_204_NO_CONTENT)

        list_after = self.client.get(self.list_url)
        for result in list_after.data['results']:
            self.assertNotEqual(result['id'], member_id)

    def test_permission_hierarchy_write_access(self):
        roles_expected = [
            (self.organization.owner, http_status.HTTP_200_OK),
            (
                MemberFactory(
                    organization=self.organization,
                    role=MemberRoleChoices.ADMIN,
                ),
                http_status.HTTP_200_OK,
            ),
            (
                MemberFactory(
                    organization=self.organization,
                    role=MemberRoleChoices.MANAGER,
                ),
                http_status.HTTP_403_FORBIDDEN,
            ),
            (
                MemberFactory(
                    organization=self.organization,
                    role=MemberRoleChoices.MEMBER,
                ),
                http_status.HTTP_403_FORBIDDEN,
            ),
        ]

        for index, (auth_member, expected_status) in enumerate(roles_expected):
            with self.subTest(member=auth_member.role):
                target = MemberFactory(
                    organization=self.organization,
                    role=MemberRoleChoices.MEMBER,
                )
                self.client.force_authenticate(member=auth_member)
                detail_url = self._detail_url(target)
                response = self.client.patch(
                    detail_url,
                    data={'nickname': f'updated_{index}'},
                    format='json',
                )
                self.assertEqual(
                    response.status_code,
                    expected_status,
                    (
                        f'{auth_member.role} expected {expected_status},'
                        f' got {response.status_code}'
                    ),
                )

    def test_permission_hierarchy_read_access(self):
        target = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        detail_url = self._detail_url(target)

        roles = [
            self.organization.owner,
            MemberFactory(organization=self.organization, role=MemberRoleChoices.ADMIN),
            MemberFactory(
                organization=self.organization, role=MemberRoleChoices.MANAGER
            ),
            MemberFactory(
                organization=self.organization, role=MemberRoleChoices.MEMBER
            ),
        ]

        for member in roles:
            with self.subTest(member=member.role):
                self.client.force_authenticate(member=member)
                response = self.client.get(detail_url)
                self.assertEqual(
                    response.status_code,
                    http_status.HTTP_200_OK,
                    f'{member.role} expected 200, got {response.status_code}',
                )

    def test_create_with_invite_then_choices_reflects(self):
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
            'nickname': 'choices_test',
        }
        create_url = reverse(self.create_with_invite_url_name, args=[invite.key])
        self.client.post(create_url, data=payload, format='json')

        choices_url = reverse('accounts:members-choices')
        choices_resp = self.client.get(choices_url)
        self.assertEqual(choices_resp.status_code, http_status.HTTP_200_OK)
        self.assertGreaterEqual(choices_resp.data['count'], 2)
