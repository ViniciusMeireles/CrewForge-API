from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
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

LIST = reverse('accounts:stored_files-list')


def _file(**access):
    def url(case):
        stored_file = StoredFileFactory.create(
            organization=case.organization,
            owner=case.organization.owner.user,
            **access,
        )
        return reverse(
            'accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )

    return url


def _rename(case):
    return {'name': 'Updated'}


class StoredFilePermissionMatrixTestCase(
    PermissionMatrixMixin, APITestCaseMixin, APITestCase
):
    actions = {
        'list': Action('get', lambda case: LIST),
        'view_public_file': Action('get', _file(public=True)),
        'view_owner_only_file': Action('get', _file()),
        'update_owner_only_file': Action('patch', _file(), _rename, 'multipart'),
        'view_members_file': Action('get', _file(org_members=True)),
        'view_managers_file': Action('get', _file(org_managers=True)),
        'view_admins_file': Action('get', _file(org_admins=True)),
        'view_owners_file': Action('get', _file(org_owners=True)),
    }
    matrix = {
        ANONYMOUS: {
            'list': 200,
            'view_public_file': 200,
            'view_owner_only_file': 404,
        },
        OWNER: {
            'view_owner_only_file': 200,
            'update_owner_only_file': 200,
            'view_owners_file': 200,
        },
        ADMIN: {'view_admins_file': 200, 'view_owners_file': 404},
        MANAGER: {'view_managers_file': 200, 'view_admins_file': 404},
        MEMBER: {'view_members_file': 200, 'view_managers_file': 404},
        INACTIVE: {'view_admins_file': 404},
        OTHER_ORGANIZATION: {'view_members_file': 404},
    }

    def setUp(self):
        self.organization = OrganizationFactory()


class StoredFilePermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.owner_user = self.organization.owner.user
        self.owner_member = self.organization.owner
        self.list_url = reverse(viewname='accounts:stored_files-list')

    def test_owner_file_other_user_cannot_view(self):
        other_user = UserFactory()
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        self.client.force_authenticate(user=other_user)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_superuser_does_not_see_other_users_files(self):
        StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        superuser = UserFactory(is_superuser=True, is_staff=True)
        self.client.force_authenticate(user=superuser)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_superuser_cannot_retrieve_other_users_file(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        superuser = UserFactory(is_superuser=True, is_staff=True)
        self.client.force_authenticate(user=superuser)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_superuser_member_sees_files_of_its_role_only(self):
        stored_file = StoredFileFactory.create(
            org_admins=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        user = UserFactory(is_superuser=True, is_staff=True)
        member = MemberFactory(organization=self.organization, user=user, role='member')
        self.client.force_authenticate(member=member)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_owner_file_no_owner_404(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=None,
        )
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_owner_file_other_user_cannot_update(self):
        other_user = UserFactory()
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        self.client.force_authenticate(user=other_user)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        payload = {'name': 'Hacked'}
        response = self.client.patch(url, payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
