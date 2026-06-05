import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import StoredFileAccess
from apps.accounts.tests.mixins import APITestCaseMixin


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class StoredFileDownloadTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.owner_user = self.organization.owner.user

    def test_download_inline(self):
        txt_file = SimpleUploadedFile(
            'download_test.txt',
            b'File content for download',
            content_type='text/plain',
        )
        payload = {
            'file': txt_file,
            'viewing_permission': StoredFileAccess.OWNER,
            'updating_permission': StoredFileAccess.OWNER,
            'owner': self.owner_user.id,
        }
        create_resp = self.client.post(
            reverse(viewname='accounts:stored_files-list'),
            payload,
            format='multipart',
        )
        self.assertEqual(create_resp.status_code, http_status.HTTP_201_CREATED)
        file_uuid = create_resp.data['uuid']
        url = reverse(viewname='accounts:stored_files-file', kwargs={'uuid': file_uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('inline', response.get('Content-Disposition', ''))

    def test_download_attachment(self):
        txt_file = SimpleUploadedFile(
            'attach_test.txt',
            b'Attachment content',
            content_type='text/plain',
        )
        payload = {
            'file': txt_file,
            'viewing_permission': StoredFileAccess.PUBLIC,
            'updating_permission': StoredFileAccess.PUBLIC,
        }
        create_resp = self.client.post(
            reverse(viewname='accounts:stored_files-list'),
            payload,
            format='multipart',
        )
        self.assertEqual(create_resp.status_code, http_status.HTTP_201_CREATED)
        file_uuid = create_resp.data['uuid']
        url = reverse(viewname='accounts:stored_files-file', kwargs={'uuid': file_uuid})
        response = self.client.get(url, {'download': 'true'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('attachment', response.get('Content-Disposition', ''))

    def test_download_content_type(self):
        txt_file = SimpleUploadedFile(
            'ctype_test.txt',
            b'Content type test',
            content_type='text/plain',
        )
        payload = {
            'file': txt_file,
            'viewing_permission': StoredFileAccess.PUBLIC,
            'updating_permission': StoredFileAccess.PUBLIC,
        }
        create_resp = self.client.post(
            reverse(viewname='accounts:stored_files-list'),
            payload,
            format='multipart',
        )
        file_uuid = create_resp.data['uuid']
        url = reverse(viewname='accounts:stored_files-file', kwargs={'uuid': file_uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'text/plain')

    def test_download_nonexistent_file(self):
        url = reverse(
            'accounts:stored_files-file',
            kwargs={'uuid': '00000000-0000-0000-0000-000000000000'},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_download_public_file_anonymous(self):
        txt_file = SimpleUploadedFile(
            'anon_test.txt',
            b'Anonymous download',
            content_type='text/plain',
        )
        payload = {
            'file': txt_file,
            'viewing_permission': StoredFileAccess.PUBLIC,
            'updating_permission': StoredFileAccess.PUBLIC,
        }
        create_resp = self.client.post(
            reverse(viewname='accounts:stored_files-list'),
            payload,
            format='multipart',
        )
        self.assertEqual(create_resp.status_code, http_status.HTTP_201_CREATED)
        file_uuid = create_resp.data['uuid']
        self.client.logout()
        url = reverse(viewname='accounts:stored_files-file', kwargs={'uuid': file_uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
