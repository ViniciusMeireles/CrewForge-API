from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationProfileFilterTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.profile = self.organization.get_profile()
        self.profile.website = 'https://example.com'
        self.profile.description = 'Main organization profile'
        self.profile.save(update_fields=['website', 'description'])
        self.list_url = reverse(viewname='accounts:organization_profiles-list')

    def test_filter_website_exact(self):
        response = self.client.get(self.list_url, {'website': 'https://example.com'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_website_exact_no_match(self):
        response = self.client.get(
            self.list_url, {'website': 'https://nonexistent.com'}
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_filter_website_icontains(self):
        response = self.client.get(self.list_url, {'website__icontains': 'example'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_description_exact(self):
        response = self.client.get(
            self.list_url, {'description': 'Main organization profile'}
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_description_icontains(self):
        response = self.client.get(
            self.list_url, {'description__icontains': 'organization'}
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_order_by_website_ascending(self):
        response = self.client.get(self.list_url, {'order_by': 'website'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        websites = [r['website'] for r in response.data['results']]
        self.assertEqual(websites, sorted(websites))

    def test_filter_order_by_website_descending(self):
        response = self.client.get(self.list_url, {'order_by': '-website'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        websites = [r['website'] for r in response.data['results']]
        self.assertEqual(websites, sorted(websites, reverse=True))

    def test_filter_order_by_description_ascending(self):
        response = self.client.get(self.list_url, {'order_by': 'description'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        descriptions = [r['description'] for r in response.data['results']]
        self.assertEqual(descriptions, sorted(descriptions))

    def test_filter_order_by_description_descending(self):
        response = self.client.get(self.list_url, {'order_by': '-description'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        descriptions = [r['description'] for r in response.data['results']]
        self.assertEqual(descriptions, sorted(descriptions, reverse=True))

    def test_filter_order_by_invalid_field(self):
        response = self.client.get(self.list_url, {'order_by': 'bogus'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_filter_order_by_with_website_filter(self):
        response = self.client.get(
            self.list_url,
            {'order_by': 'description', 'website__icontains': 'example'},
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for r in response.data['results']:
            self.assertIn('example', r['website'])
