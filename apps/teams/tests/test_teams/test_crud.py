from django.urls import reverse
from django.utils.text import slugify
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory


class TeamCRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('teams:teams-list')

    def _detail_url(self, team):
        return reverse('teams:teams-detail', args=[team.id])

    def _team_payload(self, **overrides):
        team_data = TeamFactory.build()
        payload = {
            'name': team_data.name,
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
        self.assertEqual(response.data['slug'], slugify(payload['name']))
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

    def test_create_team_without_name(self):
        payload = self._team_payload()
        del payload['name']
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_team_with_name_without_letters_or_numbers(self):
        payload = self._team_payload()
        payload['name'] = '!!!'
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data['error']['details'])

    def test_member_count_ignores_inactive_organization_members(self):
        team = TeamFactory(organization=self.organization)
        TeamMemberFactory(organization=self.organization, team=team)
        TeamMemberFactory(
            organization=self.organization,
            team=team,
            member=MemberFactory(organization=self.organization, is_active=False),
        )
        response = self.client.get(self.list_url)
        result = next(r for r in response.data['results'] if r['id'] == team.id)
        self.assertEqual(result['member_count'], 1)

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
