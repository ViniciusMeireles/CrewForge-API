import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import StoredFileAccess
from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.tests.mixins import APITestCaseMixin


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class StoredFileIntegrationTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.owner_user = self.organization.owner.user
        self.list_url = reverse(viewname='accounts:stored_files-list')

    def test_full_upload_download_flow(self):
        content = b'Full integration test content'
        txt_file = SimpleUploadedFile(
            'integration.txt',
            content,
            content_type='text/plain',
        )
        payload = {
            'file': txt_file,
            'name': 'Integration Test',
            'viewing_permission': StoredFileAccess.OWNER,
            'updating_permission': StoredFileAccess.OWNER,
            'owner': self.owner_user.id,
        }
        create_resp = self.client.post(self.list_url, payload, format='multipart')
        self.assertEqual(create_resp.status_code, http_status.HTTP_201_CREATED)
        file_uuid = create_resp.data['uuid']

        list_resp = self.client.get(self.list_url)
        self.assertEqual(list_resp.status_code, http_status.HTTP_200_OK)
        self.assertGreaterEqual(list_resp.data['count'], 1)

        detail_url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': file_uuid}
        )
        detail_resp = self.client.get(detail_url)
        self.assertEqual(detail_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(detail_resp.data['name'], 'Integration Test')

        file_url = reverse(
            viewname='accounts:stored_files-file', kwargs={'uuid': file_uuid}
        )
        download_resp = self.client.get(file_url)
        self.assertEqual(download_resp.status_code, http_status.HTTP_200_OK)

    def test_permission_change_affects_visibility(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.owner_user,
        )
        member = MemberFactory(
            organization=self.organization,
            role='member',
        )
        detail_url = reverse(
            viewname='accounts:stored_files-detail',
            kwargs={'uuid': stored_file.uuid},
        )

        self.client.force_authenticate(member=member)
        before = self.client.get(detail_url)
        self.assertEqual(before.status_code, http_status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(member=self.organization.owner)
        update_resp = self.client.patch(
            detail_url,
            {
                'viewing_permission': StoredFileAccess.PUBLIC,
                'updating_permission': StoredFileAccess.PUBLIC,
            },
            format='multipart',
        )
        self.assertEqual(update_resp.status_code, http_status.HTTP_200_OK)

        self.client.force_authenticate(member=member)
        after = self.client.get(detail_url)
        self.assertEqual(after.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            after.data['viewing_permission'],
            StoredFileAccess.PUBLIC,
        )

    def test_org_permission_hierarchy(self):
        admin = MemberFactory(organization=self.organization, role='admin')
        manager = MemberFactory(organization=self.organization, role='manager')
        member = MemberFactory(organization=self.organization, role='member')

        members_file = StoredFileFactory.create(
            org_members=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        managers_file = StoredFileFactory.create(
            org_managers=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        admins_file = StoredFileFactory.create(
            org_admins=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        owners_file = StoredFileFactory.create(
            org_owners=True,
            organization=self.organization,
            owner=self.owner_user,
        )
        files = {
            'members': members_file,
            'managers': managers_file,
            'admins': admins_file,
            'owners': owners_file,
        }

        test_cases = [
            (
                'member',
                member,
                {'members': 200, 'managers': 404, 'admins': 404, 'owners': 404},
            ),
            (
                'manager',
                manager,
                {'members': 200, 'managers': 200, 'admins': 404, 'owners': 404},
            ),
            (
                'admin',
                admin,
                {'members': 200, 'managers': 200, 'admins': 200, 'owners': 404},
            ),
        ]

        for role_name, test_member, expectations in test_cases:
            with self.subTest(role=role_name):
                self.client.force_authenticate(member=test_member)
                for file_key, expected_status in expectations.items():
                    f = files[file_key]
                    url = reverse(
                        viewname='accounts:stored_files-detail',
                        kwargs={'uuid': f.uuid},
                    )
                    response = self.client.get(url)
                    err_msg = (
                        f'{role_name} accessing {file_key}: '
                        f'expected {expected_status}, got {response.status_code}'
                    )
                    self.assertEqual(
                        response.status_code,
                        expected_status,
                        err_msg,
                    )
