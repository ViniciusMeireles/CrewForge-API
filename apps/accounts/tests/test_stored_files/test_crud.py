import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import StoredFileAccess
from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class StoredFileCRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse(viewname='accounts:stored_files-list')
        self.owner_user = self.organization.owner.user

    def test_create_file_owner_permission(self):
        txt_file = SimpleUploadedFile(
            name='test.txt',
            content=b'Hello, World!',
            content_type='text/plain',
        )
        payload = {
            'file': txt_file,
            'name': 'My File',
            'viewing_permission': StoredFileAccess.OWNER.value,
            'updating_permission': StoredFileAccess.OWNER.value,
            'owner': self.owner_user.id,
        }
        response = self.client.post(self.list_url, payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'My File')
        self.assertEqual(response.data['original_name'], 'test.txt')
        self.assertEqual(response.data['viewing_permission'], StoredFileAccess.OWNER)

    def test_create_file_public_permission(self):
        txt_file = SimpleUploadedFile(
            name='test.txt',
            content=b'Public file',
            content_type='text/plain',
        )
        payload = {
            'file': txt_file,
            'viewing_permission': StoredFileAccess.PUBLIC.value,
            'updating_permission': StoredFileAccess.PUBLIC.value,
        }
        response = self.client.post(
            path=self.list_url,
            data=payload,
            format='multipart',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['viewing_permission'], StoredFileAccess.PUBLIC)

    def test_create_file_auto_detects_content_type(self):
        txt_file = SimpleUploadedFile(
            name='test.txt',
            content=b'Hello',
            content_type='text/plain',
        )
        payload = {
            'file': txt_file,
            'viewing_permission': StoredFileAccess.PUBLIC.value,
            'updating_permission': StoredFileAccess.PUBLIC.value,
        }
        response = self.client.post(
            path=self.list_url,
            data=payload,
            format='multipart',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['content_type'], 'text/plain')

    def test_create_file_auto_organization(self):
        txt_file = SimpleUploadedFile(
            name='test.txt',
            content=b'Hello',
            content_type='text/plain',
        )
        payload = {
            'file': txt_file,
            'viewing_permission': StoredFileAccess.PUBLIC.value,
            'updating_permission': StoredFileAccess.PUBLIC.value,
        }
        response = self.client.post(
            path=self.list_url,
            data=payload,
            format='multipart',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['organization']['id'], self.organization.id)

    def test_create_file_member_within_role(self):
        member = MemberFactory(
            organization=self.organization,
            role='admin',
        )
        self.client.force_authenticate(member=member)
        txt_file = SimpleUploadedFile(
            name='test.txt',
            content=b'Hello',
            content_type='text/plain',
        )
        payload = {
            'file': txt_file,
            'viewing_permission': StoredFileAccess.ADMINS_ORGANIZATION.value,
            'updating_permission': StoredFileAccess.ADMINS_ORGANIZATION.value,
        }
        response = self.client.post(
            path=self.list_url,
            data=payload,
            format='multipart',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(
            response.data['viewing_permission'],
            StoredFileAccess.ADMINS_ORGANIZATION,
        )

    def test_create_file_permission_exceeds_role(self):
        member = MemberFactory(
            organization=self.organization,
            role='member',
        )
        self.client.force_authenticate(member=member)
        txt_file = SimpleUploadedFile(
            name='test.txt',
            content=b'Hello',
            content_type='text/plain',
        )
        payload = {
            'file': txt_file,
            'viewing_permission': StoredFileAccess.ADMINS_ORGANIZATION.value,
            'updating_permission': StoredFileAccess.ADMINS_ORGANIZATION.value,
        }
        response = self.client.post(
            path=self.list_url,
            data=payload,
            format='multipart',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_file_unauthenticated(self):
        self.client.logout()
        txt_file = SimpleUploadedFile(
            name='test.txt', content=b'Hello', content_type='text/plain'
        )
        payload = {'file': txt_file}
        response = self.client.post(self.list_url, payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_create_file_inactive_member(self):
        member = MemberFactory(
            organization=self.organization,
            is_active=False,
        )
        self.client.force_authenticate(member=member)
        txt_file = SimpleUploadedFile(
            name='test.txt', content=b'Hello', content_type='text/plain'
        )
        payload = {'file': txt_file}
        response = self.client.post(self.list_url, payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_create_file_no_owner_for_owner_permission(self):
        txt_file = SimpleUploadedFile(
            name='test.txt', content=b'Hello', content_type='text/plain'
        )
        payload = {
            'file': txt_file,
            'viewing_permission': StoredFileAccess.OWNER.value,
            'updating_permission': StoredFileAccess.OWNER.value,
        }
        response = self.client.post(self.list_url, payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_list_files(self):
        StoredFileFactory.create_batch(
            3,
            organization=self.organization,
            owner=self.owner_user,
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)

    def test_list_shows_only_visible_to_anonymous(self):
        StoredFileFactory.create(public=True, organization=self.organization)
        StoredFileFactory.create(organization=self.organization, owner=self.owner_user)
        self.client.force_authenticate(user=None)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_list_shows_owner_and_public_to_authenticated(self):
        StoredFileFactory.create(public=True, organization=self.organization)
        StoredFileFactory.create(organization=self.organization, owner=self.owner_user)
        StoredFileFactory.create(
            organization=self.organization,
            owner=UserFactory(),
        )
        self.client.logout()
        self.client.force_authenticate(user=self.owner_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_retrieve_file(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['uuid'], str(stored_file.uuid))

    def test_retrieve_nonexistent_uuid(self):
        url = reverse(
            'accounts:stored_files-detail',
            kwargs={'uuid': '00000000-0000-0000-0000-000000000000'},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_update_file_name(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        payload = {'name': 'Updated Name'}
        response = self.client.patch(url, payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Name')

    def test_partial_update_permission(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        payload = {
            'viewing_permission': StoredFileAccess.PUBLIC.value,
            'updating_permission': StoredFileAccess.PUBLIC.value,
        }
        response = self.client.patch(url, payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['viewing_permission'], StoredFileAccess.PUBLIC)

    def test_delete_file(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        stored_file.refresh_from_db()
        self.assertFalse(stored_file.is_active)

    def test_choices_endpoint(self):
        StoredFileFactory.create_batch(
            3,
            organization=self.organization,
            owner=self.owner_user,
        )
        url = reverse(viewname='accounts:stored_files-choices')
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
        result = response.data['results'][0]
        self.assertIn('value', result)
        self.assertIn('label', result)
