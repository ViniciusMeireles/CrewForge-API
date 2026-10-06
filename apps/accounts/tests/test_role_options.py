from unittest import mock

from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.accounts.utils.requests import get_member

ALL_ROLES = set(MemberRoleChoices.values)
ADMIN_ROLES = {MemberRoleChoices.MANAGER, MemberRoleChoices.MEMBER}


def _role_values(response, field_name: str = 'role') -> set:
    return {option['value'] for option in response.data[field_name]}


class AssignableByTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()

    def test_assignable_roles_per_role(self):
        expected = {
            MemberRoleChoices.OWNER: ALL_ROLES,
            MemberRoleChoices.ADMIN: ADMIN_ROLES,
            MemberRoleChoices.MANAGER: {MemberRoleChoices.MEMBER},
            MemberRoleChoices.MEMBER: set(),
        }
        for role, roles in expected.items():
            with self.subTest(role=role):
                member = MemberFactory(organization=self.organization, role=role)
                self.assertEqual(set(MemberRoleChoices.assignable_by(member)), roles)

    def test_inactive_or_missing_member_assigns_nothing(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.assertEqual(MemberRoleChoices.assignable_by(member), [])
        self.assertEqual(MemberRoleChoices.assignable_by(None), [])


class InvitationRoleOptionsTestCase(APITestCaseMixin, APITestCase):
    urls = (
        ('accounts:invitations-form-options-create', 'role'),
        ('accounts:invitations-form-options-update', 'role'),
        ('accounts:invitations-filter-options', 'role'),
        ('accounts:invitations-filter-options', 'role__in'),
    )

    def setUp(self):
        self.organization = self.new_account()

    def _assert_roles(self, expected: set):
        for url_name, field_name in self.urls:
            with self.subTest(url=url_name, field=field_name):
                response = self.client.get(reverse(url_name), {field_name: ''})
                self.assertEqual(response.status_code, http_status.HTTP_200_OK)
                self.assertEqual(_role_values(response, field_name), expected)

    def test_owner_gets_every_role(self):
        self._assert_roles(ALL_ROLES)

    def test_admin_gets_manager_and_member(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        self._assert_roles(ADMIN_ROLES)

    def test_member_is_looked_up_once_per_response(self):
        with mock.patch(
            'apps.accounts.serializers.options.get_member', wraps=get_member
        ) as spy:
            response = self.client.get(reverse('accounts:invitations-filter-options'))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(_role_values(response, 'role__in'), ALL_ROLES)
        self.assertEqual(spy.call_count, 1)

    def test_search_applies_after_permission(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        response = self.client.get(
            reverse('accounts:invitations-form-options-create'), {'role': 'o|e'}
        )
        self.assertEqual(_role_values(response), ADMIN_ROLES)


class MemberRoleOptionsTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.update_role_url = reverse('accounts:members-form-options-update-role')
        self.filter_url = reverse('accounts:members-filter-options')

    def _login(self, role):
        member = MemberFactory(organization=self.organization, role=role)
        self.client.force_authenticate(member=member)

    def test_update_role_options_per_requester(self):
        expected = {
            MemberRoleChoices.ADMIN: ADMIN_ROLES,
            MemberRoleChoices.MANAGER: {MemberRoleChoices.MEMBER},
            MemberRoleChoices.MEMBER: set(),
        }
        response = self.client.get(self.update_role_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(set(response.data), {'role'})
        self.assertEqual(_role_values(response), ALL_ROLES)
        for role, roles in expected.items():
            with self.subTest(role=role):
                self._login(role)
                response = self.client.get(self.update_role_url)
                self.assertEqual(response.status_code, http_status.HTTP_200_OK)
                self.assertEqual(_role_values(response), roles)

    def test_update_role_options_status_matches_update_role(self):
        self.client.logout()
        response = self.client.get(self.update_role_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.client.force_authenticate(user=self.organization.owner.user)
        response = self.client.get(self.update_role_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_inactive_member_gets_same_status_as_update_role(self):
        target = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        inactive = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
            is_active=False,
        )
        self.client.force_authenticate(member=inactive)
        options_status = self.client.get(self.update_role_url).status_code
        update_status = self.client.patch(
            reverse('accounts:members-update-role', args=[target.pk]),
            {'role': MemberRoleChoices.MANAGER},
        ).status_code
        self.assertEqual(options_status, http_status.HTTP_403_FORBIDDEN)
        self.assertEqual(options_status, update_status)

    def test_filter_options_keep_every_role(self):
        self._login(MemberRoleChoices.MEMBER)
        response = self.client.get(self.filter_url, {'role__in': ''})
        self.assertEqual(_role_values(response, 'role__in'), ALL_ROLES)


class ReceivedInvitationFilterOptionsTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account(organization_login=False)
        self.url = reverse('accounts:invitations-filter-options-received')

    def test_user_without_organization_session(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(set(response.data), {'role', 'role__in', 'order_by'})
        self.assertEqual(_role_values(response), ALL_ROLES)
        self.assertEqual(_role_values(response, 'role__in'), ALL_ROLES)

    def test_member_role_gets_every_role(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        response = self.client.get(self.url, {'role': ''})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(_role_values(response), ALL_ROLES)

    def test_status_matches_received_list(self):
        inactive = MemberFactory(organization=self.organization, is_active=False)
        list_url = reverse('accounts:invitations-received')
        for label, login in (
            ('user', lambda: None),
            (
                'inactive member',
                lambda: self.client.force_authenticate(member=inactive),
            ),
            ('anonymous', self.client.logout),
        ):
            with self.subTest(label):
                login()
                self.assertEqual(
                    self.client.get(self.url).status_code,
                    self.client.get(list_url).status_code,
                )

    def test_anonymous(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
