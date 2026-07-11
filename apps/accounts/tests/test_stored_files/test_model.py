import mimetypes

import uuid6
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.choices import StoredFileAccess
from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.models.files import StoredFile, upload_to_storage_files


def _upload_to_instance():
    """Return a mock-like StoredFile instance with uuid for upload_to tests."""
    return StoredFileFactory.build(organization=None, owner=None)


class StoredFileModelTestCase(APITestCase):
    """Tests for StoredFile model behavior (save, properties, upload_to)."""

    @classmethod
    def setUpTestData(cls):
        cls.org = OrganizationFactory()
        cls.owner_user = cls.org.owner.user

    def test_upload_to_with_extension(self):
        instance = _upload_to_instance()
        path = upload_to_storage_files(instance, 'test.txt')
        self.assertIn('text/plain', path)
        self.assertTrue(path.endswith('.txt'))
        self.assertIn('stored/files/', path)
        parts = path.split('/')
        self.assertEqual(len(parts), 8)

    def test_upload_to_without_extension(self):
        instance = _upload_to_instance()
        path = upload_to_storage_files(instance, 'test')
        self.assertIn('application/octet-stream', path)
        self.assertFalse(path.endswith('.'))

    def test_upload_to_double_extension(self):
        instance = _upload_to_instance()
        path = upload_to_storage_files(instance, 'archive.tar.gz')
        self.assertTrue(path.split('/')[-1].endswith('.gz'))

    def test_upload_to_date_format(self):
        instance = _upload_to_instance()
        path = upload_to_storage_files(instance, 'test.txt')
        parts = path.split('/')
        date_parts = [p for p in parts if p.isdigit()]
        self.assertEqual(len(date_parts[0]), 4)
        self.assertEqual(len(date_parts[1]), 2)
        self.assertEqual(len(date_parts[2]), 2)

    def test_save_populates_original_name(self):
        stored_file = StoredFileFactory.create(
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.original_name, 'test.txt')

    def test_save_populates_content_type(self):
        stored_file = StoredFileFactory.create(
            txt=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'text/plain')

    def test_save_populates_size(self):
        stored_file = StoredFileFactory.create(
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertGreater(stored_file.size, 0)

    def test_save_pdf_content_type(self):
        stored_file = StoredFileFactory.create(
            pdf=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'application/pdf')

    def test_save_png_content_type(self):
        stored_file = StoredFileFactory.create(
            png=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'image/png')

    def test_save_jpg_content_type(self):
        stored_file = StoredFileFactory.create(
            jpg=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'image/jpeg')

    def test_save_gif_content_type(self):
        stored_file = StoredFileFactory.create(
            gif=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'image/gif')

    def test_save_webp_content_type(self):
        stored_file = StoredFileFactory.create(
            webp=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'image/webp')

    def test_save_svg_content_type(self):
        stored_file = StoredFileFactory.create(
            svg=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'image/svg+xml')

    def test_save_csv_content_type(self):
        stored_file = StoredFileFactory.create(
            csv=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'text/csv')

    def test_save_html_content_type(self):
        stored_file = StoredFileFactory.create(
            html=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'text/html')

    def test_save_json_content_type(self):
        stored_file = StoredFileFactory.create(
            json=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'application/json')

    def test_save_xml_content_type(self):
        stored_file = StoredFileFactory.create(
            xml=True,
            organization=self.org,
            owner=self.owner_user,
        )
        expected, _ = mimetypes.guess_type('test.xml')
        self.assertEqual(stored_file.content_type, expected)

    def test_save_zip_content_type(self):
        stored_file = StoredFileFactory.create(
            zip=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'application/zip')

    def test_save_gz_content_type(self):
        stored_file = StoredFileFactory.create(
            gz=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'application/x-tar')

    def test_save_no_ext_content_type(self):
        stored_file = StoredFileFactory.create(
            no_ext=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'application/octet-stream')

    def test_save_bin_content_type(self):
        stored_file = StoredFileFactory.create(
            bin_=True,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.content_type, 'application/octet-stream')

    def test_save_does_not_overwrite_original_name(self):
        stored_file = StoredFileFactory.create(
            organization=self.org,
            owner=self.owner_user,
            original_name='custom_name.txt',
        )
        self.assertEqual(stored_file.original_name, 'custom_name.txt')

    def test_save_does_not_overwrite_content_type(self):
        stored_file = StoredFileFactory.create(
            txt=True,
            organization=self.org,
            owner=self.owner_user,
        )
        original_ct = stored_file.content_type
        stored_file.name = 'Updated'
        stored_file.save()
        stored_file.refresh_from_db()
        self.assertEqual(stored_file.content_type, original_ct)

    def test_save_no_file_does_not_raise(self):
        stored_file = StoredFile(
            name='no-file',
            viewing_permission=StoredFileAccess.OWNER,
            updating_permission=StoredFileAccess.OWNER,
            owner=self.owner_user,
            organization=self.org,
        )
        stored_file.save()
        self.assertEqual(stored_file.original_name, '')
        self.assertEqual(stored_file.content_type, '')
        self.assertEqual(stored_file.size, 0)

    def test_download_name_uses_name(self):
        stored_file = StoredFileFactory.create(
            txt=True,
            name='document',
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.download_name, 'document.txt')

    def test_download_name_fallback_original(self):
        stored_file = StoredFileFactory.create(
            txt=True,
            name=None,
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.download_name, 'test.txt')

    def test_download_name_fallback_uuid(self):
        stored_file = StoredFile(
            file=SimpleUploadedFile('test', b'data', content_type='text/plain'),
            name=None,
            original_name='',
            content_type='text/plain',
            viewing_permission=StoredFileAccess.OWNER,
            updating_permission=StoredFileAccess.OWNER,
        )
        stored_file.uuid = uuid6.uuid7()
        actual = stored_file.download_name
        self.assertIn(str(stored_file.uuid), actual)

    def test_download_name_no_bin_extension(self):
        stored_file = StoredFileFactory.create(
            no_ext=True,
            name='data',
            content_type='application/octet-stream',
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.download_name, 'data')

    def test_download_name_suppresses_bin_in_original(self):
        stored_file = StoredFileFactory.create(
            bin_=True,
            name='doc',
            original_name='test.bin',
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.download_name, 'doc')

    def test_download_name_already_has_ext(self):
        stored_file = StoredFileFactory.create(
            name='file.txt',
            organization=self.org,
            owner=self.owner_user,
        )
        self.assertEqual(stored_file.download_name, 'file.txt')

    def test_file_path_returns_url(self):
        stored_file = StoredFileFactory.create(
            organization=self.org,
            owner=self.owner_user,
        )
        expected_path = reverse(
            viewname='accounts:stored_files-file',
            kwargs={'uuid': stored_file.uuid},
        )
        self.assertEqual(stored_file.file_path, expected_path)

    def test_str_with_name(self):
        stored_file = StoredFileFactory.create(
            name='Test File',
            organization=self.org,
            owner=self.owner_user,
        )
        expected = f'{stored_file.uuid} - Test File'
        self.assertEqual(str(stored_file), expected)

    def test_str_without_name(self):
        stored_file = StoredFileFactory.create(
            name=None,
            organization=self.org,
            owner=self.owner_user,
        )
        expected = f'{stored_file.uuid} - {stored_file.original_name}'
        self.assertEqual(str(stored_file), expected)

    def test_label_expression_with_name(self):
        stored_file = StoredFileFactory.create(
            name='My File',
            organization=self.org,
            owner=self.owner_user,
        )
        expr = StoredFile.label_expression()
        queryset = StoredFile.objects.filter(id=stored_file.id).annotate(label=expr)
        self.assertEqual(queryset.first().label, 'My File')

    def test_label_expression_without_name(self):
        stored_file = StoredFileFactory.create(
            name=None,
            organization=self.org,
            owner=self.owner_user,
        )
        expr = StoredFile.label_expression()
        queryset = StoredFile.objects.filter(id=stored_file.id).annotate(label=expr)
        self.assertEqual(queryset.first().label, stored_file.original_name)
