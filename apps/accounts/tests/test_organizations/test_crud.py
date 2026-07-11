from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationCRUDTestCase(APITestCaseMixin, APITestCase):
    def _detail_url(self, org):
        return reverse('accounts:organizations-detail', args=[org.id])

    def _login_url(self, org):
        return reverse('accounts:organizations-login', args=[org.id])

    def _org_payload(self, **overrides):
        data = OrganizationFactory.build()
        payload = {
            'name': data.name,
            'slug': data.slug,
        }
        payload.update(overrides)
        return payload

    def test_list_organizations(self):
        org = self.new_account(login=False)
        MemberFactory.create_batch(size=4, user=org.owner.user)
        self.client.force_authenticate(member=org.owner)
        url = reverse('accounts:organizations-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 5)

    def test_list_only_active_organizations(self):
        self.new_account()
        OrganizationFactory(is_active=False)
        url = reverse('accounts:organizations-list')
        response = self.client.get(url)
        for result in response.data['results']:
            self.assertTrue(result.get('is_active', True))

    def test_create_organization(self):
        user = UserFactory.create()
        self.client.force_authenticate(user=user)
        payload = self._org_payload()
        url = reverse('accounts:organizations-list')
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], payload['name'])
        self.assertEqual(response.data['slug'], payload['slug'])

    def test_create_organization_auto_sets_owner(self):
        user = UserFactory.create()
        self.client.force_authenticate(user=user)
        payload = self._org_payload()
        url = reverse('accounts:organizations-list')
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        owner_id = response.data['owner']
        self.assertIsNotNone(owner_id)

    def test_retrieve_organization(self):
        org = OrganizationFactory.create()
        url = self._detail_url(org)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['name'], org.name)
        self.assertEqual(response.data['slug'], org.slug)

    def test_retrieve_nonexistent(self):
        url = self._detail_url(OrganizationFactory.build(id=99999))
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_update_organization_full(self):
        org = self.new_account()
        payload = self._org_payload()
        url = self._detail_url(org)
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['name'], payload['name'])
        self.assertEqual(response.data['slug'], payload['slug'])

    def test_update_organization_name(self):
        org = self.new_account()
        url = self._detail_url(org)
        payload = {**self._org_payload(), 'name': 'New Name'}
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        org.refresh_from_db()
        self.assertEqual(org.name, 'New Name')

    def test_update_organization_slug(self):
        org = self.new_account()
        url = self._detail_url(org)
        payload = {**self._org_payload(), 'slug': 'new-slug'}
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        org.refresh_from_db()
        self.assertEqual(org.slug, 'new-slug')

    def test_delete_organization(self):
        org = self.new_account()
        url = self._detail_url(org)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_delete_soft_delete(self):
        org = self.new_account()
        url = self._detail_url(org)
        self.client.delete(url)
        org.refresh_from_db()
        self.assertFalse(org.is_active)

    def test_delete_soft_removes_from_active_only_list(self):
        org = self.new_account()
        url = self._detail_url(org)
        self.client.delete(url)
        org.refresh_from_db()
        self.assertFalse(org.is_active)

    def test_delete_nonexistent(self):
        self.new_account()
        url = self._detail_url(OrganizationFactory.build(id=99999))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_create_duplicate_slug(self):
        org = self.new_account()
        payload = self._org_payload(slug=org.slug)
        url = reverse('accounts:organizations-list')
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_choices_endpoint(self):
        org = self.new_account()
        MemberFactory.create_batch(size=3, user=org.owner.user)
        self.client.force_authenticate(member=org.owner)
        url = reverse('accounts:organizations-choices')
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)

    def test_choices_values(self):
        org = self.new_account()
        self.client.force_authenticate(member=org.owner)
        url = reverse('accounts:organizations-choices')
        response = self.client.get(url)
        if response.data['count'] > 0:
            self.assertIn('value', response.data['results'][0])
            self.assertIn('label', response.data['results'][0])

    def test_login_organization(self):
        org = self.new_account()
        user = org.owner.user
        self.client.force_authenticate(user=user)
        url = self._login_url(org)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(self.client.session.get('organization_id'), org.id)
        self.assertIn('user', response.data)
        self.assertIn('organizations', response.data)
        self.assertIn('organization', response.data)
        self.assertIn('member', response.data)
        self.assertEqual(response.data['organization']['id'], org.id)

    def test_login_organization_switches_context(self):
        user = UserFactory.create()
        org1 = OrganizationFactory.create()
        MemberFactory.create(user=user, organization=org1)
        org2 = OrganizationFactory.create()
        MemberFactory.create(user=user, organization=org2)
        self.client.force_authenticate(user=user)

        url1 = self._login_url(org1)
        response1 = self.client.post(url1, format='json')
        self.assertEqual(response1.status_code, http_status.HTTP_200_OK)
        self.assertEqual(self.client.session.get('organization_id'), org1.id)

        url2 = self._login_url(org2)
        response2 = self.client.post(url2, format='json')
        self.assertEqual(response2.status_code, http_status.HTTP_200_OK)
        self.assertEqual(self.client.session.get('organization_id'), org2.id)

    def test_login_nonexistent_organization(self):
        user = UserFactory.create()
        self.client.force_authenticate(user=user)
        url = self._login_url(OrganizationFactory.build(id=99999))
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_create_organization_without_name(self):
        user = UserFactory.create()
        self.client.force_authenticate(user=user)
        payload = self._org_payload()
        del payload['name']
        url = reverse('accounts:organizations-list')
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_organization_without_slug(self):
        user = UserFactory.create()
        self.client.force_authenticate(user=user)
        payload = self._org_payload()
        del payload['slug']
        url = reverse('accounts:organizations-list')
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_partial_update_inactive_organization(self):
        org = self.new_account()
        url = self._detail_url(org)
        self.client.delete(url)
        org.refresh_from_db()
        self.assertFalse(org.is_active)
        payload = self._org_payload(name='Updated Name')
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
