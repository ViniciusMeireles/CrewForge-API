from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
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

    def test_filter_my_organizations_true(self):
        response = self.client.get(self.list_url, {'my_organizations': 'true'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.organization.id)

    def test_filter_my_organizations_false(self):
        response = self.client.get(self.list_url, {'my_organizations': 'false'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 4)

    def test_filter_my_organizations_excludes_inactive_members(self):
        user = UserFactory.create()
        org = OrganizationFactory.create()
        MemberFactory.create(user=user, organization=org, is_active=False)
        self.client.force_authenticate(user=user)
        response = self.client.get(self.list_url, {'my_organizations': 'true'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_filter_my_organizations_unauthenticated(self):
        self.client.logout()
        response = self.client.get(self.list_url, {'my_organizations': 'true'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 4)

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

    def test_filter_order_by_slug_ascending(self):
        response = self.client.get(self.list_url, {'order_by': 'slug'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        slugs = [r['slug'] for r in response.data['results']]
        self.assertEqual(slugs, sorted(slugs))

    def test_filter_order_by_slug_descending(self):
        response = self.client.get(self.list_url, {'order_by': '-slug'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        slugs = [r['slug'] for r in response.data['results']]
        self.assertEqual(slugs, sorted(slugs, reverse=True))

    def test_filter_order_by_invalid_field(self):
        response = self.client.get(self.list_url, {'order_by': 'invalid'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_filter_order_by_with_name_filter(self):
        response = self.client.get(
            self.list_url,
            {'order_by': 'slug', 'name__icontains': 'corp'},
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
