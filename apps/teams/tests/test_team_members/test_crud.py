from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory


class TeamMemberCRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('teams:team_members-list')
        self.choices_url = reverse('teams:team_members-choices')

    def _detail_url(self, tm):
        return reverse('teams:team_members-detail', args=[tm.id])

    def _tm_payload(self, **overrides):
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {
            'team': team.id,
            'member': member.id,
            'role': TeamMemberRoleChoices.MEMBER,
        }
        payload.update(overrides)
        return payload

    def test_list_team_members(self):
        TeamMemberFactory.create_batch(size=5, organization=self.organization)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 5)

    def test_list_only_active(self):
        TeamMemberFactory(organization=self.organization, is_active=False)
        response = self.client.get(self.list_url)
        self.assertEqual(response.data['count'], 0)

    def test_list_organization_scoped(self):
        other_org = OrganizationFactory()
        TeamMemberFactory(organization=self.organization)
        TeamMemberFactory(organization=other_org)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_create_team_member(self):
        payload = self._tm_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['team'], payload['team'])
        self.assertEqual(response.data['member'], payload['member'])
        self.assertEqual(response.data['role'], payload['role'])

    def test_create_team_member_with_default_role(self):
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {'team': team.id, 'member': member.id}
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], TeamMemberRoleChoices.MEMBER)

    def test_create_team_member_missing_team(self):
        member = MemberFactory(organization=self.organization)
        payload = {'member': member.id, 'role': TeamMemberRoleChoices.MEMBER}
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_team_member_missing_member(self):
        team = TeamFactory(organization=self.organization)
        payload = {'team': team.id, 'role': TeamMemberRoleChoices.MEMBER}
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_retrieve_team_member(self):
        tm = TeamMemberFactory(organization=self.organization)
        url = self._detail_url(tm)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['id'], tm.id)

    def test_retrieve_nonexistent(self):
        url = self._detail_url(TeamMemberFactory.build(id=99999))
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_retrieve_inactive_team_member(self):
        tm = TeamMemberFactory(organization=self.organization, is_active=False)
        url = self._detail_url(tm)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_update_team_member_role(self):
        tm = TeamMemberFactory(organization=self.organization)
        new_role = TeamMemberRoleChoices.ADMIN
        payload = {'role': new_role}
        url = self._detail_url(tm)
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['role'], new_role)

    def test_update_team_member_full(self):
        tm = TeamMemberFactory(organization=self.organization)
        payload = {'role': TeamMemberRoleChoices.ADMIN}
        url = self._detail_url(tm)
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_update_team_member_invalid_role(self):
        tm = TeamMemberFactory(organization=self.organization)
        url = self._detail_url(tm)
        payload = {'role': 'not_a_valid_role'}
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_delete_team_member(self):
        tm = TeamMemberFactory(organization=self.organization)
        url = self._detail_url(tm)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_delete_soft_delete(self):
        tm = TeamMemberFactory(organization=self.organization)
        url = self._detail_url(tm)
        self.client.delete(url)
        tm.refresh_from_db()
        self.assertFalse(tm.is_active)

    def test_delete_removes_from_list(self):
        tm = TeamMemberFactory(organization=self.organization)
        url = self._detail_url(tm)
        self.client.delete(url)
        response = self.client.get(self.list_url)
        for result in response.data['results']:
            self.assertNotEqual(result['id'], tm.id)

    def test_delete_nonexistent(self):
        url = self._detail_url(TeamMemberFactory.build(id=99999))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_delete_and_recreate(self):
        tm = TeamMemberFactory(organization=self.organization)
        url = self._detail_url(tm)
        self.client.delete(url)
        payload = {
            'team': tm.team.id,
            'member': tm.member.id,
            'role': tm.role,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_create_duplicate_team_member(self):
        tm = TeamMemberFactory(organization=self.organization)
        payload = {
            'team': tm.team.id,
            'member': tm.member.id,
            'role': TeamMemberRoleChoices.MEMBER,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_choices_endpoint(self):
        TeamMemberFactory.create_batch(size=3, organization=self.organization)
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)

    def test_choices_values(self):
        TeamMemberFactory(organization=self.organization)
        response = self.client.get(self.choices_url)
        if response.data['count'] > 0:
            self.assertIn('value', response.data['results'][0])
            self.assertIn('label', response.data['results'][0])
