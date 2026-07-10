from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.factories.teams import TeamFactory


class TeamIntegrationTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('teams:teams-list')

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

    def _model_url(self, team_id):
        return self._detail_url(TeamFactory._meta.model(id=team_id))

    def test_full_crud_flow(self):
        payload = self._team_payload()
        create_resp = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(create_resp.status_code, http_status.HTTP_201_CREATED)
        team_id = create_resp.data['id']
        self.assertEqual(create_resp.data['name'], payload['name'])

        retrieve_resp = self.client.get(self._model_url(team_id))
        self.assertEqual(retrieve_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(retrieve_resp.data['id'], team_id)

        update_payload = self._team_payload()
        update_resp = self.client.put(
            self._model_url(team_id),
            data=update_payload,
            format='json',
        )
        self.assertEqual(update_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(update_resp.data['name'], update_payload['name'])

        delete_resp = self.client.delete(self._model_url(team_id))
        self.assertEqual(delete_resp.status_code, http_status.HTTP_204_NO_CONTENT)

        list_after = self.client.get(self.list_url)
        for result in list_after.data['results']:
            self.assertNotEqual(result['id'], team_id)

    def test_team_org_isolation(self):
        team = TeamFactory(organization=self.organization)
        other_org = OrganizationFactory()
        other_member = other_org.owner

        self.client.force_authenticate(member=other_member)
        list_resp = self.client.get(self.list_url)
        self.assertEqual(list_resp.status_code, http_status.HTTP_200_OK)
        for result in list_resp.data['results']:
            self.assertNotEqual(result['id'], team.id)

        detail_resp = self.client.get(self._detail_url(team))
        self.assertEqual(detail_resp.status_code, http_status.HTTP_404_NOT_FOUND)
