import tempfile

from django.test import override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class StoredFilePermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.owner_user = self.organization.owner.user
        self.owner_member = self.organization.owner
        self.list_url = reverse(viewname='accounts:stored_files-list')

    def test_public_file_anonymous_can_view(self):
        stored_file = StoredFileFactory.create(
            public=True,
            organization=self.organization,
        )
        self.client.force_authenticate(user=None)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_file_owner_can_view(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

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

    def test_owner_file_anonymous_cannot_view(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        self.client.force_authenticate(user=None)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_superuser_can_view_any_file(self):
        StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        superuser = UserFactory(is_superuser=True, is_staff=True)
        self.client.force_authenticate(user=superuser)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_member_can_view_members_file(self):
        member = MemberFactory(organization=self.organization, role='member')
        stored_file = StoredFileFactory.create(
            org_members=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        self.client.force_authenticate(member=member)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_member_cannot_view_managers_file(self):
        member = MemberFactory(organization=self.organization, role='member')
        stored_file = StoredFileFactory.create(
            org_managers=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        self.client.force_authenticate(member=member)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_manager_can_view_managers_file(self):
        manager = MemberFactory(organization=self.organization, role='manager')
        stored_file = StoredFileFactory.create(
            org_managers=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        self.client.force_authenticate(member=manager)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_manager_cannot_view_admins_file(self):
        manager = MemberFactory(organization=self.organization, role='manager')
        stored_file = StoredFileFactory.create(
            org_admins=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        self.client.force_authenticate(member=manager)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_admin_can_view_admins_file(self):
        admin = MemberFactory(organization=self.organization, role='admin')
        stored_file = StoredFileFactory.create(
            org_admins=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        self.client.force_authenticate(member=admin)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_cannot_view_owners_file(self):
        admin = MemberFactory(organization=self.organization, role='admin')
        stored_file = StoredFileFactory.create(
            org_owners=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        self.client.force_authenticate(member=admin)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_owner_can_view_owners_file(self):
        stored_file = StoredFileFactory.create(
            org_owners=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_inactive_member_cannot_access(self):
        member = MemberFactory(
            organization=self.organization,
            role='admin',
            is_active=False,
        )
        stored_file = StoredFileFactory.create(
            org_admins=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        self.client.force_authenticate(member=member)
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_member_cannot_access(self):
        other_org = OrganizationFactory()
        other_member = other_org.owner
        stored_file = StoredFileFactory.create(
            org_members=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        self.client.force_authenticate(member=other_member)
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

    def test_owner_file_owner_can_update(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        payload = {'name': 'Updated'}
        response = self.client.patch(url, payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

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

    def test_not_authenticated_list(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
