from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.factories.teams import TeamFactory


class TeamFilterTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('teams:teams-list')

        self.alpha_team = TeamFactory(
            organization=self.organization,
            name='Alpha Team',
            slug='alpha-team',
        )
        self.beta_team = TeamFactory(
            organization=self.organization,
            name='Beta Team',
            slug='beta-team',
        )
        self.gamma_team = TeamFactory(
            organization=self.organization,
            name='Gamma Squad',
            slug='gamma-squad',
        )

    def test_filter_name_exact(self):
        response = self.client.get(self.list_url, {'name': 'Alpha Team'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['name'], 'Alpha Team')

    def test_filter_name_icontains(self):
        response = self.client.get(self.list_url, {'name__icontains': 'team'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_filter_slug_exact(self):
        response = self.client.get(self.list_url, {'slug': 'beta-team'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['slug'], 'beta-team')

    def test_filter_slug_icontains(self):
        response = self.client.get(self.list_url, {'slug__icontains': 'team'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
