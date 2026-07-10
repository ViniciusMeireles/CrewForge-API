from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationFilterTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:organizations-list')

        self.alpha_org = OrganizationFactory(name='Alpha Corp', slug='alpha-corp')
        self.beta_org = OrganizationFactory(name='Beta Inc', slug='beta-inc')
        self.gamma_org = OrganizationFactory(name='Gamma LLC', slug='gamma-llc')

    def test_filter_name_exact(self):
        response = self.client.get(self.list_url, {'name': 'Alpha Corp'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_name_icontains(self):
        response = self.client.get(self.list_url, {'name__icontains': 'corp'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_slug_exact(self):
        response = self.client.get(self.list_url, {'slug': 'beta-inc'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_slug_icontains(self):
        response = self.client.get(self.list_url, {'slug__icontains': 'llc'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
