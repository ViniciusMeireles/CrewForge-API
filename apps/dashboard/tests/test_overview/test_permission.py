from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.accounts.tests.permission_matrix import (
    ADMIN,
    ANONYMOUS,
    INACTIVE,
    MANAGER,
    MEMBER,
    NO_SESSION,
    OWNER,
    Action,
    PermissionMatrixMixin,
)

OVERVIEW = reverse('dashboard:overview')


class OverviewPermissionMatrixTestCase(
    PermissionMatrixMixin, APITestCaseMixin, APITestCase
):
    actions = {'overview': Action('get', lambda case: OVERVIEW)}
    matrix = {
        ANONYMOUS: {'overview': 401},
        NO_SESSION: {'overview': 403},
        INACTIVE: {'overview': 403},
        OWNER: {'overview': 200},
        ADMIN: {'overview': 200},
        MANAGER: {'overview': 200},
        MEMBER: {'overview': 200},
    }

    def setUp(self):
        self.organization = OrganizationFactory()


class OverviewPermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.url = reverse('dashboard:overview')
        self.organization = self.new_account(login=False)

    def _login_as(self, role, **kwargs):
        member = MemberFactory(
            organization=self.organization,
            role=role,
            replace_owner=role == MemberRoleChoices.OWNER,
            **kwargs,
        )
        self.client.force_authenticate(member=member)
        return member

    def test_write_methods_not_allowed(self):
        self._login_as(MemberRoleChoices.OWNER)
        for method in ('post', 'put', 'patch', 'delete', 'head'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url, format='json')
                self.assertEqual(
                    response.status_code,
                    http_status.HTTP_405_METHOD_NOT_ALLOWED,
                )

    def test_section_gates_by_role(self):
        for role in MemberRoleChoices.values:
            with self.subTest(role=role):
                self._login_as(role)
                data = self.client.get(self.url).data
                self.assertIsNotNone(data['members'])
                self.assertIsNotNone(data['teams'])
                self.assertEqual(
                    data['invitations'] is not None,
                    role in (MemberRoleChoices.OWNER, MemberRoleChoices.ADMIN),
                )

    def test_owner_session_payload_sections_not_null(self):
        self.client.force_authenticate(member=self.organization.owner)
        data = self.client.get(self.url).data
        self.assertIsNotNone(data['members'])
        self.assertIsNotNone(data['teams'])
        self.assertIsNotNone(data['invitations'])
        self.assertIn('pending', data['received_invitations'])
