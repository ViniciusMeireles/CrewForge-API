from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationProfileSerializerTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.profile = self.organization.get_profile()
        self.list_url = reverse(viewname='accounts:organization_profiles-list')
        self.detail_url = reverse(
            viewname='accounts:organization_profiles-detail',
            args=[self.profile.id],
        )

    def test_list_serializer_fields(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        result = response.data['results'][0]
        expected_fields = {
            'id',
            'website',
            'description',
            'organization',
        }
        self.assertEqual(set(result.keys()), expected_fields)

    def test_detail_serializer_fields(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        expected_fields = {
            'id',
            'website',
            'description',
            'organization',
        }
        self.assertEqual(set(response.data.keys()), expected_fields)

    def test_read_only_fields_ignored_on_update(self):
        payload = {
            'website': 'https://example.com',
            'description': 'Updated description',
            'id': 9999,
            'is_active': False,
        }
        response = self.client.put(self.detail_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.id, 9999)
        self.assertTrue(self.profile.is_active)

    def test_update_website(self):
        payload = {'website': 'https://new-website.com'}
        response = self.client.patch(self.detail_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.website, 'https://new-website.com')

    def test_update_description(self):
        payload = {'description': 'New description'}
        response = self.client.patch(self.detail_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.description, 'New description')

    def test_update_full(self):
        payload = {
            'website': 'https://full-update.com',
            'description': 'Full update description',
        }
        response = self.client.put(self.detail_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.website, 'https://full-update.com')
        self.assertEqual(self.profile.description, 'Full update description')

    def test_update_nonexistent(self):
        url = reverse(viewname='accounts:organization_profiles-detail', args=[99999])
        payload = {'website': 'https://example.com'}
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_organization_is_read_only(self):
        from apps.accounts.factories.organizations import OrganizationFactory

        other_org = OrganizationFactory()
        payload = {'organization': other_org.id}
        response = self.client.patch(self.detail_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.organization_id, self.organization.id)

    def test_updated_by_on_update(self):
        payload = {'website': 'https://test.com'}
        response = self.client.patch(self.detail_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.profile.refresh_from_db()
        owner_user = self.organization.owner.user
        self.assertEqual(self.profile.updated_by_id, owner_user.id)

    def test_created_by_is_none_for_factory_created(self):
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.created_by_id)
