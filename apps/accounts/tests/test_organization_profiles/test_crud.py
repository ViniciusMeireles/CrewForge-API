from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationProfileCRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.profile = self.organization.get_profile()
        self.list_url = reverse(viewname='accounts:organization_profiles-list')
        self.choices_url = reverse(viewname='accounts:organization_profiles-choices')

    def _detail_url(self, profile):
        return reverse(
            viewname='accounts:organization_profiles-detail',
            args=[profile.id],
        )

    def test_list_profiles(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_list_only_active(self):
        self.profile.is_active = False
        self.profile.save(update_fields=['is_active'])
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_retrieve_profile(self):
        url = self._detail_url(self.profile)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.profile.id)

    def test_retrieve_nonexistent(self):
        url = reverse(viewname='accounts:organization_profiles-detail', args=[99999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_update_profile_full(self):
        url = self._detail_url(self.profile)
        payload = {
            'website': 'https://updated.com',
            'description': 'Updated description',
        }
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.website, 'https://updated.com')
        self.assertEqual(self.profile.description, 'Updated description')

    def test_partial_update_website(self):
        url = self._detail_url(self.profile)
        response = self.client.patch(
            url,
            data={'website': 'https://partial.com'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.website, 'https://partial.com')

    def test_partial_update_description(self):
        url = self._detail_url(self.profile)
        response = self.client.patch(
            url,
            data={'description': 'Partial description'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.description, 'Partial description')

    def test_delete_profile(self):
        url = self._detail_url(self.profile)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_delete_soft_delete(self):
        url = self._detail_url(self.profile)
        self.client.delete(url)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_active)

    def test_delete_removes_from_list(self):
        url = self._detail_url(self.profile)
        self.client.delete(url)
        response = self.client.get(self.list_url)
        self.assertEqual(response.data['count'], 0)

    def test_delete_nonexistent(self):
        url = reverse(viewname='accounts:organization_profiles-detail', args=[99999])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_choices_endpoint(self):
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)

    def test_choices_values(self):
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
        result = response.data['results'][0]
        self.assertIn('value', result)
        self.assertIn('label', result)
        self.assertEqual(result['label'], self.organization.name)
