from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin

INTERNAL = {'suspended_at', 'suspended_by', 'suspension_reason'}


class OrganizationSuspensionFieldsTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.url = reverse('accounts:organizations-detail', args=[self.organization.id])

    def test_detail_hides_internal_suspension_fields(self):
        data = self.client.get(self.url).data
        self.assertEqual(data['status'], 'active')
        self.assertFalse(INTERNAL & set(data))

    def test_owner_cannot_change_the_status(self):
        response = self.client.patch(
            self.url,
            data={'status': 'suspended', 'suspension_reason': 'x'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.status, 'active')
        self.assertEqual(self.organization.suspension_reason, '')
        self.assertFalse(INTERNAL & set(response.data))
