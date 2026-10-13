from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin


class OverviewI18nTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.url = reverse('dashboard:overview')
        self.organization = self.new_account()

    def test_role_labels_translated_to_pt_br(self):
        response = self.client.get(
            self.url,
            HTTP_ACCEPT_LANGUAGE='pt-BR,pt;q=0.9',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.headers['Content-Language'], 'pt-br')
        labels = [row['role_label'] for row in response.data['members']['by_role']]
        self.assertEqual(
            labels,
            ['Proprietário', 'Administrador', 'Gerente', 'Membro'],
        )
        self.assertEqual(response.data['member']['role_label'], 'Proprietário')

    def test_role_labels_default_english(self):
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        labels = [row['role_label'] for row in response.data['members']['by_role']]
        self.assertEqual(labels, ['Owner', 'Admin', 'Manager', 'Member'])
