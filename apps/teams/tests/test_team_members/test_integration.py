from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory


class TeamMemberIntegrationTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('teams:team_members-list')

    def test_full_crud_flow(self):
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {
            'team': team.id,
            'member': member.id,
            'role': TeamMemberRoleChoices.MEMBER,
        }
        create_resp = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(create_resp.status_code, http_status.HTTP_201_CREATED)
        tm_id = create_resp.data['id']

        retrieve_resp = self.client.get(
            reverse('teams:team_members-detail', args=[tm_id])
        )
        self.assertEqual(retrieve_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(retrieve_resp.data['id'], tm_id)

        update_payload = {'role': TeamMemberRoleChoices.ADMIN}
        update_resp = self.client.put(
            reverse('teams:team_members-detail', args=[tm_id]),
            data=update_payload,
            format='json',
        )
        self.assertEqual(update_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(update_resp.data['role'], TeamMemberRoleChoices.ADMIN)

        delete_resp = self.client.delete(
            reverse('teams:team_members-detail', args=[tm_id])
        )
        self.assertEqual(delete_resp.status_code, http_status.HTTP_204_NO_CONTENT)

        list_after = self.client.get(self.list_url)
        for result in list_after.data['results']:
            self.assertNotEqual(result['id'], tm_id)

    def test_team_member_org_isolation(self):
        other_org = OrganizationFactory()
        other_owner = other_org.owner
        tm = TeamMemberFactory(organization=self.organization)
        self.client.force_authenticate(member=other_owner)
        response = self.client.get(reverse('teams:team_members-detail', args=[tm.id]))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
