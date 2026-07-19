from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory


class TeamMemberFilterTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('teams:team_members-list')

    def test_filter_team_exact(self):
        team = TeamFactory(organization=self.organization)
        TeamMemberFactory(organization=self.organization, team=team)
        TeamMemberFactory(organization=self.organization)
        response = self.client.get(self.list_url, {'team': team.id})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_member_exact(self):
        member = MemberFactory(organization=self.organization)
        TeamMemberFactory(organization=self.organization, member=member)
        TeamMemberFactory(organization=self.organization)
        response = self.client.get(self.list_url, {'member': member.id})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_role_exact(self):
        TeamMemberFactory(
            organization=self.organization, role=TeamMemberRoleChoices.ADMIN
        )
        TeamMemberFactory(
            organization=self.organization, role=TeamMemberRoleChoices.MEMBER
        )
        response = self.client.get(self.list_url, {'role': TeamMemberRoleChoices.ADMIN})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_order_by_role_ascending(self):
        TeamMemberFactory.create_batch(size=3, organization=self.organization)
        response = self.client.get(self.list_url, {'order_by': 'role'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        roles = [r['role'] for r in response.data['results']]
        self.assertEqual(roles, sorted(roles))

    def test_filter_order_by_role_descending(self):
        TeamMemberFactory.create_batch(size=3, organization=self.organization)
        response = self.client.get(self.list_url, {'order_by': '-role'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        roles = [r['role'] for r in response.data['results']]
        self.assertEqual(roles, sorted(roles, reverse=True))

    def test_filter_order_by_invalid_field(self):
        TeamMemberFactory(organization=self.organization)
        response = self.client.get(self.list_url, {'order_by': 'bogus'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_filter_order_by_with_role_filter(self):
        TeamMemberFactory(
            organization=self.organization, role=TeamMemberRoleChoices.ADMIN
        )
        TeamMemberFactory(
            organization=self.organization, role=TeamMemberRoleChoices.MEMBER
        )
        response = self.client.get(
            self.list_url,
            {'order_by': 'role', 'role': TeamMemberRoleChoices.ADMIN},
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for r in response.data['results']:
            self.assertEqual(r['role'], TeamMemberRoleChoices.ADMIN)
