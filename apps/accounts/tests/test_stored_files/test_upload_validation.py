import io
from types import SimpleNamespace

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.uploadhandler import StopUpload
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import OrganizationImageTypeChoices, StoredFileAccess
from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.models.files import StoredFile
from apps.accounts.serializers.files import StoredFileCreateUpdateModelSerializer
from apps.accounts.tests.mixins import PNG_SIGNATURE, APITestCaseMixin
from apps.accounts.utils.files import TEXT, MaxSizeUploadHandler, sniff_content_type

JPEG = b'\xff\xd8\xff\xe0' + b'jpeg'
GIF = b'GIF89a' + b'gif'
WEBP = b'RIFF\x00\x00\x00\x00WEBPVP8 '
PDF = b'%PDF-1.4\n'
ZIP = b'PK\x03\x04\x14\x00zip'
OLE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1ole'
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
            b'MZ\x90\x03 executable': None,
            'relatório;ação'.encode('cp1252'): TEXT,
            b'tabs\tand\r\nnewlines': TEXT,
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
            'data.json': (b'{"a": 1}', 'application/json'),
            'bundle.zip': (ZIP, 'application/zip'),
            'contrato.docx': (
                ZIP,
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ),
            'planilha.xlsx': (
                ZIP,
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            ),
            'texto.odt': (ZIP, 'application/vnd.oasis.opendocument.text'),
            'antigo.doc': (OLE, 'application/msword'),
            'antiga.xls': (OLE, 'application/vnd.ms-excel'),
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
            'fake.docx': PNG_SIGNATURE + b'x',
            'archive.png': ZIP,
            'macro.doc': ZIP,
            'bundle.zip': OLE,
            'noext-zip': ZIP,
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                response = self.upload(name, content)
                self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
                self.assertIn('file', response.data['error']['details'])

    def test_accepts_windows_1252_csv(self):
        response = self.upload('relatorio.csv', 'nome;ação\nJoão;1'.encode('cp1252'))
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        stored = StoredFile.objects.get(uuid=response.data['uuid'])
        self.assertEqual(stored.content_type, 'text/csv')

    @override_settings(STORED_FILE_MAX_SIZE=10)
    def test_rejects_request_over_content_length_limit(self):
        response = self.client.post(
            self.url,
            {'file': SimpleUploadedFile('notes.txt', b'x' * (2 * 1024 * 1024))},
            format='multipart',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data['error']['details'])

    @override_settings(STORED_FILE_MAX_SIZE=10)
    def test_oversized_request_checks_authentication_first(self):
        self.client.logout()
        response = self.client.post(
            self.url,
            {'file': SimpleUploadedFile('notes.txt', b'x' * (2 * 1024 * 1024))},
            format='multipart',
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_dropped_upload_reports_size_error(self):
        serializer = StoredFileCreateUpdateModelSerializer(
            data={}, context={'request': SimpleNamespace(upload_too_large=True)}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('too large', str(serializer.errors['file'][0]))

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

    @override_settings(STORED_FILE_MAX_SIZE=10)
    def test_oversized_request_error_is_nested_under_image(self):
        response = self.upload('logo.png', PNG_SIGNATURE + b'x' * (2 * 1024 * 1024))
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data['error']['details']['image'])

    def test_only_raster_images(self):
        for name, content in {
            'logo.svg': SVG,
            'logo.pdf': PDF,
            'logo.txt': b'text',
        }.items():
            with self.subTest(name=name):
                response = self.upload(name, content)
                self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)


class MaxSizeUploadHandlerTestCase(SimpleTestCase):
    @override_settings(STORED_FILE_MAX_SIZE=10)
    def test_stops_when_file_exceeds_limit(self):
        handler = MaxSizeUploadHandler()
        handler.new_file('file', 'big.txt', 'text/plain', 20)
        self.assertEqual(handler.receive_data_chunk(b'x' * 10, 0), b'x' * 10)
        with self.assertRaises(StopUpload):
            handler.receive_data_chunk(b'x', 10)

    @override_settings(STORED_FILE_MAX_SIZE=10)
    def test_counts_each_file_separately(self):
        handler = MaxSizeUploadHandler()
        handler.new_file('file', 'a.txt', 'text/plain', 8)
        handler.receive_data_chunk(b'x' * 8, 0)
        handler.new_file('file', 'b.txt', 'text/plain', 8)
        self.assertEqual(handler.receive_data_chunk(b'x' * 8, 0), b'x' * 8)


class StoredFileContentTypeOnSaveTestCase(TestCase):
    def test_replacing_the_file_recomputes_the_type_from_bytes(self):
        stored = StoredFileFactory(
            file=ContentFile(PNG_SIGNATURE + b'x', name='logo.png'),
        )
        self.assertEqual(stored.content_type, 'image/png')

        stored = StoredFile.objects.get(pk=stored.pk)
        stored.file = ContentFile(PDF, name='report')
        stored.save()
        self.assertEqual(stored.content_type, 'application/pdf')

    def test_keeps_type_when_file_is_unchanged(self):
        stored = StoredFileFactory(
            file=ContentFile(PNG_SIGNATURE + b'x', name='logo.png'),
        )
        stored = StoredFile.objects.get(pk=stored.pk)
        stored.name = 'renamed'
        stored.save()
        self.assertEqual(stored.content_type, 'image/png')
