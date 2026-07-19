from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class StoredFileFilterTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse(viewname='accounts:stored_files-list')
        StoredFileFactory.create(
            txt=True,
            name='alpha.txt',
            organization=self.organization,
            owner=self.organization.owner.user,
        )
        StoredFileFactory.create(
            txt=True,
            name='beta.txt',
            organization=self.organization,
            owner=self.organization.owner.user,
        )
        StoredFileFactory.create(
            pdf=True,
            name='report.pdf',
            organization=self.organization,
            owner=self.organization.owner.user,
        )

    def test_filter_name_exact(self):
        response = self.client.get(self.list_url, data={'name': 'alpha.txt'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_name_icontains(self):
        response = self.client.get(self.list_url, data={'name__icontains': 'report'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_content_type_exact(self):
        response = self.client.get(
            self.list_url, data={'content_type': 'application/pdf'}
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_viewing_permission_exact(self):
        response = self.client.get(self.list_url, data={'viewing_permission': 'owner'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_filter_viewing_permission_in(self):
        response = self.client.get(
            self.list_url,
            data={'viewing_permission__in': 'owner,public'},
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)

    def test_filter_order_by_name_ascending(self):
        response = self.client.get(self.list_url, {'order_by': 'name'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        names = [r['name'] for r in response.data['results']]
        self.assertEqual(names, sorted(names))

    def test_filter_order_by_name_descending(self):
        response = self.client.get(self.list_url, {'order_by': '-name'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        names = [r['name'] for r in response.data['results']]
        self.assertEqual(names, sorted(names, reverse=True))

    def test_filter_order_by_size_ascending(self):
        response = self.client.get(self.list_url, {'order_by': 'size'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        sizes = [r['size'] for r in response.data['results']]
        self.assertEqual(sizes, sorted(sizes))

    def test_filter_order_by_size_descending(self):
        response = self.client.get(self.list_url, {'order_by': '-size'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        sizes = [r['size'] for r in response.data['results']]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_filter_order_by_invalid_field(self):
        response = self.client.get(self.list_url, {'order_by': 'bogus'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_filter_order_by_with_content_type_filter(self):
        response = self.client.get(
            self.list_url,
            {'order_by': 'name', 'content_type': 'text/plain'},
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for r in response.data['results']:
            self.assertEqual(r['content_type'], 'text/plain')
