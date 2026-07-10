from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.factories.teams import TeamFactory


class TeamCRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('teams:teams-list')
        self.choices_url = reverse('teams:teams-choices')

    def _detail_url(self, team):
        return reverse('teams:teams-detail', args=[team.id])

    def _team_payload(self, **overrides):
        team_data = TeamFactory.build()
        payload = {
            'name': team_data.name,
            'slug': team_data.slug,
            'description': team_data.description,
        }
        payload.update(overrides)
        return payload

    def test_list_teams(self):
        TeamFactory.create_batch(size=5, organization=self.organization)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 5)

    def test_list_only_active(self):
        TeamFactory(organization=self.organization, is_active=False)
        TeamFactory(organization=self.organization)
        response = self.client.get(self.list_url)
        for result in response.data['results']:
            self.assertTrue(result['is_active'])

    def test_create_team(self):
        payload = self._team_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], payload['name'])
        self.assertEqual(response.data['slug'], payload['slug'])
        self.assertEqual(response.data['description'], payload['description'])
        self.assertEqual(response.data['organization'], self.organization.id)

    def test_retrieve_team(self):
        team = TeamFactory(organization=self.organization)
        url = self._detail_url(team)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['id'], team.id)

    def test_retrieve_nonexistent(self):
        url = self._detail_url(TeamFactory.build(id=99999))
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_update_team_full(self):
        team = TeamFactory(organization=self.organization)
        payload = self._team_payload()
        url = self._detail_url(team)
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['name'], payload['name'])
        self.assertEqual(response.data['slug'], payload['slug'])
        self.assertEqual(response.data['description'], payload['description'])

    def test_delete_team(self):
        team = TeamFactory(organization=self.organization)
        url = self._detail_url(team)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_delete_soft_delete(self):
        team = TeamFactory(organization=self.organization)
        url = self._detail_url(team)
        self.client.delete(url)
        team.refresh_from_db()
        self.assertFalse(team.is_active)

    def test_delete_removes_from_list(self):
        team = TeamFactory(organization=self.organization)
        url = self._detail_url(team)
        self.client.delete(url)
        response = self.client.get(self.list_url)
        for result in response.data['results']:
            self.assertNotEqual(result['id'], team.id)

    def test_delete_nonexistent(self):
        url = self._detail_url(TeamFactory.build(id=99999))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_create_duplicate_slug_in_same_org(self):
        team = TeamFactory(organization=self.organization)
        payload = self._team_payload(slug=team.slug)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_choices_endpoint(self):
        TeamFactory.create_batch(size=3, organization=self.organization)
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        if response.data['count'] > 0:
            self.assertIn('value', response.data['results'][0])
            self.assertIn('label', response.data['results'][0])

    def test_create_team_without_name(self):
        payload = self._team_payload()
        del payload['name']
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_team_without_slug(self):
        payload = self._team_payload()
        del payload['slug']
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_partial_update_inactive_team(self):
        team = TeamFactory(organization=self.organization, is_active=False)
        url = self._detail_url(team)
        payload = self._team_payload()
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_list_organization_scoped(self):
        TeamFactory(organization=self.organization)
        other_org = OrganizationFactory()
        TeamFactory(organization=other_org)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        for result in response.data['results']:
            self.assertEqual(result['organization'], self.organization.id)

    def test_retrieve_inactive_team(self):
        team = TeamFactory(organization=self.organization, is_active=False)
        url = self._detail_url(team)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
