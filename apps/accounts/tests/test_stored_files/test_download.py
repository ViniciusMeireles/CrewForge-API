from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import StoredFileAccess
from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.models.files import StoredFile
from apps.accounts.tests.mixins import PNG_SIGNATURE, APITestCaseMixin


class StoredFileDownloadTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.owner_user = self.organization.owner.user

    def upload(self, name, content, permission=StoredFileAccess.OWNER):
        response = self.client.post(
            reverse(viewname='accounts:stored_files-list'),
            {
                'file': SimpleUploadedFile(name, content),
                'viewing_permission': permission,
                'updating_permission': permission,
                'owner': self.owner_user.id,
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        return reverse(
            viewname='accounts:stored_files-file',
            kwargs={'uuid': response.data['uuid']},
        )

    def test_download_inline_for_raster_image(self):
        url = self.upload('logo.png', PNG_SIGNATURE + b'image')
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('inline', response.get('Content-Disposition', ''))
        self.assertEqual(response['Content-Type'], 'image/png')

    def test_download_image_as_attachment_when_requested(self):
        url = self.upload('logo.png', PNG_SIGNATURE + b'image')
        response = self.client.get(url, {'download': 'true'})
        self.assertIn('attachment', response.get('Content-Disposition', ''))

    def test_non_image_is_always_attachment(self):
        url = self.upload('download_test.txt', b'<script>alert(1)</script>')
        response = self.client.get(url, {'download': 'false'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('attachment', response.get('Content-Disposition', ''))

    def test_security_headers(self):
        for name, content in [
            ('logo.png', PNG_SIGNATURE + b'image'),
            ('notes.txt', b'plain text'),
        ]:
            with self.subTest(name=name):
                response = self.client.get(self.upload(name, content))
                self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
                self.assertEqual(
                    response['Content-Security-Policy'],
                    "sandbox; default-src 'none'",
                )

    def test_legacy_file_without_content_type_is_attachment(self):
        stored_file = StoredFileFactory(
            owner=self.owner_user,
            organization=self.organization,
        )
        StoredFile.objects.filter(pk=stored_file.pk).update(content_type='')
        url = reverse(
            viewname='accounts:stored_files-file', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertIn('attachment', response.get('Content-Disposition', ''))
        self.assertEqual(response['Content-Type'], 'application/octet-stream')

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
