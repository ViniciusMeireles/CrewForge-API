from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.accounts.tests.permission_matrix import (
    ADMIN,
    ANONYMOUS,
    INACTIVE,
    MANAGER,
    MEMBER,
    OTHER_ORGANIZATION,
    OWNER,
    Action,
    PermissionMatrixMixin,
)

LIST = reverse('accounts:members-list')


def _target(case):
    return MemberFactory(organization=case.organization, role=MemberRoleChoices.MEMBER)


def _detail(target):
    return lambda case: reverse('accounts:members-detail', args=[target(case).pk])


def _role(target):
    return lambda case: reverse('accounts:members-update-role', args=[target(case).pk])


def _actor(case):
    return case.actor_member


def _owner(case):
    return case.organization.owner


def _nickname(case):
    return {'nickname': 'renamed'}


def _role_payload(role):
    return lambda case: {'role': role}


class MemberPermissionMatrixTestCase(
    PermissionMatrixMixin, APITestCaseMixin, APITestCase
):
    inactive_role = MemberRoleChoices.MEMBER
    actions = {
        'list': Action('get', lambda case: LIST),
        'retrieve': Action('get', _detail(_target)),
        'update': Action('patch', _detail(_target), _nickname),
        'delete': Action('delete', _detail(_target)),
        'update_role': Action(
            'patch', _role(_target), _role_payload(MemberRoleChoices.MANAGER)
        ),
        'update_self': Action('patch', _detail(_actor), _nickname),
        'delete_self': Action('delete', _detail(_actor)),
        'update_role_self': Action(
            'patch', _role(_actor), _role_payload(MemberRoleChoices.ADMIN)
        ),
        'update_role_owner': Action(
            'patch', _role(_owner), _role_payload(MemberRoleChoices.MEMBER)
        ),
        'delete_owner': Action('delete', _detail(_owner)),
    }
    matrix = {
        ANONYMOUS: {
            'list': 401,
            'retrieve': 401,
            'update': 401,
            'delete': 401,
            'update_role': 401,
        },
        INACTIVE: {
            'list': 403,
            'retrieve': 403,
            'update': 403,
            'delete': 403,
            'update_role': 403,
        },
        OWNER: {
            'list': 200,
            'retrieve': 200,
            'update': 200,
            'delete': 204,
            'update_role_self': 403,
            'delete_self': 403,
        },
        ADMIN: {
            'list': 200,
            'retrieve': 200,
            'update': 200,
            'delete': 204,
            'update_role': 200,
            'update_role_owner': 403,
            'delete_owner': 403,
        },
        MANAGER: {
            'retrieve': 200,
            'update': 403,
            'delete': 403,
            'update_self': 200,
        },
        MEMBER: {
            'retrieve': 200,
            'update': 403,
            'delete': 403,
            'update_self': 200,
            'delete_self': 204,
        },
        OTHER_ORGANIZATION: {'retrieve': 404, 'update': 404},
    }


class MemberPermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:members-list')
        self.update_role_url_name = 'accounts:members-update-role'

    def _detail_url(self, member):
        return reverse('accounts:members-detail', args=[member.id])

    def _update_role_url(self, member):
        return reverse(self.update_role_url_name, args=[member.id])

    def _create_target_member(self, role=MemberRoleChoices.MEMBER):
        return MemberFactory(
            organization=self.organization,
            role=role,
        )

    def test_owner_protection_error_message(self):
        admin = self._create_target_member(role=MemberRoleChoices.ADMIN)
        self.client.force_authenticate(member=admin)
        response = self.client.delete(self._detail_url(self.organization.owner))
        self.assertEqual(
            str(response.data['error']['message']),
            'The Owner cannot be removed or demoted; transfer ownership first.',
        )

    def test_admin_cannot_update_role_to_owner(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        target = self._create_target_member()
        payload = {'role': MemberRoleChoices.OWNER}
        url = self._update_role_url(target)
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_cross_org_member_list_returns_empty(self):
        member = self._create_target_member()
        other_member = MemberFactory()
        self.client.force_authenticate(member=other_member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertNotEqual(result['id'], member.id)

    def test_cross_org_inactive_member_returns_404(self):
        inactive_member = MemberFactory(is_active=False)
        url = self._detail_url(inactive_member)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
