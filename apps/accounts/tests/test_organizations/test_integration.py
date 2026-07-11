from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationIntegrationTestCase(APITestCaseMixin, APITestCase):
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

    def test_create_org_then_list(self):
        payload1 = self._org_payload()
        response1 = self.client.post(self.list_url, data=payload1, format='json')
        self.assertEqual(response1.status_code, http_status.HTTP_201_CREATED)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn(response1.data['id'], [r['id'] for r in response.data['results']])

    def test_create_org_then_login(self):
        payload = self._org_payload()
        create_resp = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(create_resp.status_code, http_status.HTTP_201_CREATED)
        org_id = create_resp.data['id']
        login_url = reverse('accounts:organizations-login', args=[org_id])
        login_resp = self.client.post(login_url, format='json')
        self.assertEqual(login_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(self.client.session.get('organization_id'), org_id)

    def test_owner_only_can_delete(self):
        org = self.new_account()
        admin = MemberFactory(organization=org, role=MemberRoleChoices.ADMIN)
        self.client.force_authenticate(member=admin)
        url = self._detail_url(org)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(member=org.owner)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_full_crud_flow(self):
        org = self.new_account()
        url = self._detail_url(org)
        list_resp = self.client.get(self.list_url)
        self.assertEqual(list_resp.status_code, http_status.HTTP_200_OK)
        self.assertGreaterEqual(list_resp.data['count'], 1)

        retrieve_resp = self.client.get(url)
        self.assertEqual(retrieve_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(retrieve_resp.data['id'], org.id)

        payload = self._org_payload()
        update_resp = self.client.put(url, data=payload, format='json')
        self.assertEqual(update_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(update_resp.data['name'], payload['name'])

        delete_resp = self.client.delete(url)
        self.assertEqual(delete_resp.status_code, http_status.HTTP_204_NO_CONTENT)

        org.refresh_from_db()
        self.assertFalse(org.is_active)
