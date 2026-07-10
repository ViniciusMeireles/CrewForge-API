from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationSerializerTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:organizations-list')

    def _detail_url(self, org):
        return reverse('accounts:organizations-detail', args=[org.id])

    def _org_payload(self, **overrides):
        data = OrganizationFactory.build()
        payload = {
            'name': data.name,
            'slug': data.slug,
        }
        payload.update(overrides)
        return payload

    def test_create_serializer_fields(self):
        payload = self._org_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        expected_fields = {
            'id',
            'name',
            'slug',
            'owner',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
            'profile',
        }
        self.assertEqual(set(response.data.keys()), expected_fields)

    def test_detail_serializer_fields(self):
        url = self._detail_url(self.organization)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        expected_fields = {
            'id',
            'name',
            'slug',
            'owner',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
            'profile',
        }
        self.assertEqual(set(response.data.keys()), expected_fields)

    def test_list_serializer_fields(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        result = response.data['results'][0]
        expected_fields = {'id', 'name', 'slug', 'profile'}
        self.assertEqual(set(result.keys()), expected_fields)

    def test_validate_duplicate_slug(self):
        payload = self._org_payload(slug=self.organization.slug)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_validate_empty_name(self):
        payload = self._org_payload(name='', slug='valid-slug')
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_validate_empty_slug(self):
        payload = self._org_payload(name='Valid Name', slug='')
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_auto_populates_owner_on_create(self):
        payload = self._org_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data['owner'])

    def test_validate_name_too_long(self):
        payload = self._org_payload(name='a' * 256)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_validate_slug_too_long(self):
        payload = self._org_payload(slug='a' * 51)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_validate_name_with_special_chars(self):
        payload = self._org_payload(name='My Org #1 (test) & Co.')
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_validate_slug_with_invalid_format(self):
        payload = self._org_payload(slug='invalid slug with spaces')
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_read_only_fields_ignored(self):
        payload = self._org_payload()
        payload['id'] = 99999
        payload['is_active'] = False
        payload['created_at'] = '2020-01-01T00:00:00Z'
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertNotEqual(response.data['id'], 99999)
        self.assertTrue(response.data['is_active'])

    def test_update_read_only_fields_ignored(self):
        url = self._detail_url(self.organization)
        payload = self._org_payload()
        payload['is_active'] = False
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.organization.refresh_from_db()
        self.assertTrue(self.organization.is_active)
