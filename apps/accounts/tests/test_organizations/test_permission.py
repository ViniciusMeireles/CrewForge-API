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
    OTHER_ORGANIZATION,
    OWNER,
    Action,
    PermissionMatrixMixin,
)

LIST = reverse('accounts:organizations-list')


def _detail(case):
    return reverse('accounts:organizations-detail', args=[case.organization.pk])


def _payload(case):
    data = OrganizationFactory.build()
    return {'name': data.name, 'slug': data.slug}


class OrganizationPermissionMatrixTestCase(
    PermissionMatrixMixin, APITestCaseMixin, APITestCase
):
    inactive_role = MemberRoleChoices.MEMBER
    actions = {
        'list': Action('get', lambda case: LIST),
        'create': Action('post', lambda case: LIST, _payload),
        'retrieve': Action('get', _detail),
        'update': Action('put', _detail, _payload),
        'delete': Action('delete', _detail),
    }
    matrix = {
        ANONYMOUS: {
            'list': 401,
            'create': 401,
            'retrieve': 401,
            'update': 401,
            'delete': 401,
        },
        INACTIVE: {'create': 201, 'retrieve': 404, 'update': 404, 'delete': 404},
        OWNER: {'list': 200, 'retrieve': 200, 'update': 200, 'delete': 204},
        ADMIN: {'list': 200, 'retrieve': 200, 'update': 403, 'delete': 403},
        MANAGER: {'retrieve': 200, 'update': 403, 'delete': 403},
        MEMBER: {'retrieve': 200, 'update': 403, 'delete': 403},
        OTHER_ORGANIZATION: {'retrieve': 404, 'update': 404, 'delete': 404},
    }

    def setUp(self):
        self.organization = OrganizationFactory()


class OrganizationPermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:organizations-list')

    def _detail_url(self, org):
        return reverse('accounts:organizations-detail', args=[org.id])

    def _org_payload(self, **overrides):
        data = OrganizationFactory.build()
        payload = {
            'name': data.name,
            'slug': data.slug,
        }
        payload.update(overrides)
        return payload

    def test_not_active_member_list(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        ids = [org['id'] for org in response.data['results']]
        self.assertNotIn(self.organization.id, ids)

    def test_user_without_organization_context_retrieve_returns_404(self):
        other_org = OrganizationFactory()
        self.client.force_authenticate(user=other_org.owner.user)
        response = self.client.get(self._detail_url(self.organization))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_member_list_returns_only_own_organization(self):
        other_org = OrganizationFactory()
        other_owner = other_org.owner
        self.client.force_authenticate(member=other_owner)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        ids = [org['id'] for org in response.data['results']]
        self.assertEqual(ids, [other_org.id])

    def test_list_returns_only_active_member_organizations(self):
        user = self.organization.owner.user
        suspended = OrganizationFactory(suspended=True)
        MemberFactory(organization=suspended, user=user)
        inactive = OrganizationFactory(is_active=False)
        MemberFactory(organization=inactive, user=user)
        removed_from = OrganizationFactory()
        MemberFactory(organization=removed_from, user=user, is_active=False)
        OrganizationFactory()
        self.client.force_authenticate(user=user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        ids = {org['id'] for org in response.data['results']}
        self.assertEqual(ids, {self.organization.id, suspended.id})
