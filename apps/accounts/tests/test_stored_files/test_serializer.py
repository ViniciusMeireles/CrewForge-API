from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class StoredFileSerializerTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse(viewname='accounts:stored_files-list')

    def test_list_serializer_fields(self):
        StoredFileFactory.create(
            organization=self.organization,
            owner=self.organization.owner.user,
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        result = response.data['results'][0]
        expected_fields = {
            'uuid',
            'name',
            'original_name',
            'content_type',
            'size',
            'file_url',
            'download_name',
            'updated_at',
        }
        self.assertEqual(set(result.keys()), expected_fields)

    def test_list_serializer_file_url_present(self):
        StoredFileFactory.create(
            organization=self.organization,
            owner=self.organization.owner.user,
        )
        response = self.client.get(self.list_url)
        self.assertIsNotNone(response.data['results'][0]['file_url'])
        file_url = response.data['results'][0]['file_url']
        # self.assertIn('/api/accounts/stored-files/', file_url)
        self.assertIn(reverse(viewname='accounts:stored_files-list'), file_url)

    def test_detail_serializer_fields(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.organization.owner.user,
        )
        url = reverse(
            viewname='accounts:stored_files-detail',
            kwargs={'uuid': stored_file.uuid},
        )
        response = self.client.get(url)
        result = response.data
        expected_fields = {
            'uuid',
            'name',
            'original_name',
            'content_type',
            'size',
            'file_url',
            'download_name',
            'updated_at',
            'viewing_permission',
            'updating_permission',
            'owner',
            'organization',
        }
        self.assertEqual(set(result.keys()), expected_fields)

    def test_detail_serializer_owner_nested(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.organization.owner.user,
        )
        url = reverse(
            viewname='accounts:stored_files-detail',
            kwargs={'uuid': stored_file.uuid},
        )
        response = self.client.get(url)
        self.assertIsInstance(response.data['owner'], dict)
        self.assertEqual(
            response.data['owner']['id'],
            self.organization.owner.user.id,
        )

    def test_detail_serializer_organization_nested(self):
        stored_file = StoredFileFactory.create(
            organization=self.organization,
            owner=self.organization.owner.user,
        )
        url = reverse(
            viewname='accounts:stored_files-detail', kwargs={'uuid': stored_file.uuid}
        )
        response = self.client.get(url)
        self.assertIsInstance(response.data['organization'], dict)
