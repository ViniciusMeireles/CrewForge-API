import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import OrganizationImageTypeChoices, StoredFileAccess
from apps.accounts.models.files import StoredFile
from apps.accounts.tests.mixins import PNG_SIGNATURE, APITestCaseMixin
from apps.accounts.utils.files import TEXT, sniff_content_type

JPEG = b'\xff\xd8\xff\xe0' + b'jpeg'
GIF = b'GIF89a' + b'gif'
WEBP = b'RIFF\x00\x00\x00\x00WEBPVP8 '
PDF = b'%PDF-1.4\n'
HTML = b'<html><script>alert(1)</script></html>'
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


class SniffContentTypeTestCase(SimpleTestCase):
    def test_detects_signatures(self):
        cases = {
            PNG_SIGNATURE + b'x': 'image/png',
            JPEG: 'image/jpeg',
            GIF: 'image/gif',
            WEBP: 'image/webp',
            PDF: 'application/pdf',
            b'hello': TEXT,
            'olá'.encode(): TEXT,
            b'\x00\x01binary': None,
            b'\xff\xfe\xfd invalid utf-8': None,
        }
        for content, expected in cases.items():
            with self.subTest(content=content[:12]):
                self.assertEqual(sniff_content_type(io.BytesIO(content)), expected)

    def test_rewinds_the_file(self):
        file = io.BytesIO(PNG_SIGNATURE + b'x')
        sniff_content_type(file)
        self.assertEqual(file.tell(), 0)


class StoredFileUploadValidationTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.url = reverse(viewname='accounts:stored_files-list')

    def upload(self, name, content):
        return self.client.post(
            self.url,
            {
                'file': SimpleUploadedFile(name, content),
                'viewing_permission': StoredFileAccess.OWNER,
                'updating_permission': StoredFileAccess.OWNER,
                'owner': self.organization.owner.user_id,
            },
            format='multipart',
        )

    def test_accepts_allowed_types(self):
        cases = {
            'logo.png': (PNG_SIGNATURE + b'x', 'image/png'),
            'photo.jpg': (JPEG, 'image/jpeg'),
            'anim.gif': (GIF, 'image/gif'),
            'pic.webp': (WEBP, 'image/webp'),
            'doc.pdf': (PDF, 'application/pdf'),
            'notes.txt': (b'notes', 'text/plain'),
            'data.csv': (b'a,b\n1,2', 'text/csv'),
            'README': (b'no extension', 'text/plain'),
            'logo': (PNG_SIGNATURE + b'x', 'image/png'),
        }
        for name, (content, content_type) in cases.items():
            with self.subTest(name=name):
                response = self.upload(name, content)
                self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
                stored = StoredFile.objects.get(uuid=response.data['uuid'])
                self.assertEqual(stored.content_type, content_type)

    def test_rejects_dangerous_or_unknown_types(self):
        cases = {
            'page.html': HTML,
            'image.svg': SVG,
            'script.js': b'alert(1)',
            'app.exe': b'MZ\x00\x00binary',
            'fake.png': HTML,
            'image.jpg': PNG_SIGNATURE + b'x',
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                response = self.upload(name, content)
                self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
                self.assertIn('file', response.data['error']['details'])

    @override_settings(STORED_FILE_MAX_SIZE=10)
    def test_rejects_files_over_the_size_limit(self):
        response = self.upload('notes.txt', b'more than ten bytes')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data['error']['details'])


class OrganizationImageUploadValidationTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.url = reverse(viewname='accounts:organization_images-list')

    def upload(self, name, content):
        return self.client.post(
            self.url,
            {
                'image.file': SimpleUploadedFile(name, content),
                'image_type': OrganizationImageTypeChoices.LOGO,
            },
            format='multipart',
        )

    def test_sets_detected_content_type(self):
        response = self.upload('logo.png', PNG_SIGNATURE + b'x')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['image']['content_type'], 'image/png')

    def test_only_raster_images(self):
        for name, content in {
            'logo.svg': SVG,
            'logo.pdf': PDF,
            'logo.txt': b'text',
        }.items():
            with self.subTest(name=name):
                response = self.upload(name, content)
                self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
