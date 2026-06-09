from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory


class TeamMemberAPITestCase(APITestCaseMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.detail_url_name = 'teams:team_members-detail'
        cls.list_url_name = 'teams:team_members-list'
        cls.list_url = reverse(cls.list_url_name)
        cls.choices_url = reverse(viewname='teams:team_members-choices')

    def setUp(self):
        self.organization = self.new_account()

    def _assert_data(self, response, team_member_data):
        """Helper method to assert the response data."""
        self.assertEqual(response.data.get('team'), team_member_data.team.id)
        self.assertEqual(response.data.get('member'), team_member_data.member.id)
        self.assertEqual(response.data.get('role'), team_member_data.role)

    def test_list_and_choices_team_members(self):
        """Test listing team members."""
        TeamMemberFactory.create_batch(size=7, organization=self.organization)

        for url in [self.list_url, self.choices_url]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, http_status.HTTP_200_OK)
            self.assertEqual(response.data.get('count'), 7)

    def test_create_team_member(self):
        """Test creating a team member."""
        team = TeamFactory.create(organization=self.organization)
        member = MemberFactory.create(organization=self.organization)
        team_member_data = TeamMemberFactory.build(
            team=team, member=member, organization=self.organization
        )
        payload = {
            'team': team_member_data.team.id,
            'member': team_member_data.member.id,
            'role': team_member_data.role,
        }

        response = self.client.post(self.list_url, data=payload)
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self._assert_data(response, team_member_data)

    def test_retrieve_team_member(self):
        """Test retrieving a team member."""
        team_member = TeamMemberFactory.create(organization=self.organization)

        response = self.client.get(reverse(self.detail_url_name, args=[team_member.id]))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self._assert_data(response, team_member)

    def test_update_team_member(self):
        """Test updating a team member."""
        team_member = TeamMemberFactory.create(organization=self.organization)
        new_role = TeamMemberRoleChoices.ADMIN
        payload = {
            'role': new_role,
        }

        response = self.client.put(
            reverse(self.detail_url_name, args=[team_member.id]), data=payload
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data.get('role'), new_role)

    def test_delete_team_member(self):
        """Test deleting a team member."""
        team_member = TeamMemberFactory.create(organization=self.organization)

        response = self.client.delete(
            reverse(self.detail_url_name, args=[team_member.id])
        )
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

        # Verify that the team member no longer exists
        response = self.client.get(reverse(self.detail_url_name, args=[team_member.id]))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_delete_and_recreate_team_member(self):
        """Test deleting and recreating a team member."""
        team_member = TeamMemberFactory.create(organization=self.organization)

        # Delete the team member
        response = self.client.delete(
            reverse(self.detail_url_name, args=[team_member.id])
        )
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

        # Recreate the team member
        payload = {
            'team': team_member.team.id,
            'member': team_member.member.id,
            'role': team_member.role,
        }
        response = self.client.post(self.list_url, data=payload)
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self._assert_data(response, team_member)

    def test_not_permission_team_member(self):
        """Test that a user without permission cannot create a team member."""
        team_member = TeamMemberFactory.create(
            organization=OrganizationFactory.create()
        )

        response = self.client.get(reverse(self.detail_url_name, args=[team_member.id]))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

        # Test that a user without permission cannot update a team member
        team_member = TeamMemberFactory.create(organization=self.organization)
        simple_member = MemberFactory.create(
            organization=self.organization,
            role=MemberRoleChoices.MEMBER,
        )
        self.client.force_authenticate(member=simple_member)
        response = self.client.put(
            reverse(self.detail_url_name, args=[team_member.id]),
            data={'role': TeamMemberRoleChoices.ADMIN},
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_authenticated_list_team_members(self):
        """Test listing team members without authentication."""
        self.client.force_authenticate(member=None)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_retrieve_team_member(self):
        """Test retrieving a team member without authentication."""
        team_member = TeamMemberFactory.create(organization=self.organization)
        self.client.force_authenticate(member=None)
        response = self.client.get(reverse(self.detail_url_name, args=[team_member.id]))
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_create_team_member(self):
        """Test creating a team member without authentication."""
        team = TeamFactory.create(organization=self.organization)
        member = MemberFactory.create(organization=self.organization)
        team_member_data = TeamMemberFactory.build(
            team=team, member=member, organization=self.organization
        )
        payload = {
            'team': team_member_data.team.id,
            'member': team_member_data.member.id,
            'role': team_member_data.role,
        }
        self.client.force_authenticate(member=None)
        response = self.client.post(self.list_url, data=payload)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_update_team_member(self):
        """Test updating a team member without authentication."""
        team_member = TeamMemberFactory.create(organization=self.organization)
        new_role = TeamMemberRoleChoices.ADMIN
        payload = {
            'role': new_role,
        }
        self.client.force_authenticate(member=None)
        response = self.client.put(
            reverse(self.detail_url_name, args=[team_member.id]), data=payload
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_delete_team_member(self):
        """Test deleting a team member without authentication."""
        team_member = TeamMemberFactory.create(organization=self.organization)
        self.client.force_authenticate(member=None)
        response = self.client.delete(
            reverse(self.detail_url_name, args=[team_member.id])
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_active_member_list_team_members(self):
        """Test listing team members with an inactive member."""
        inactive_member = MemberFactory.create(
            organization=self.organization,
            is_active=False,
        )
        self.client.force_authenticate(member=inactive_member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_retrieve_team_member(self):
        """Test retrieving a team member with an inactive member."""
        team_member = TeamMemberFactory.create(organization=self.organization)
        inactive_member = MemberFactory.create(
            organization=self.organization,
            is_active=False,
        )
        self.client.force_authenticate(member=inactive_member)
        response = self.client.get(reverse(self.detail_url_name, args=[team_member.id]))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_create_team_member(self):
        """Test creating a team member with an inactive member."""
        team = TeamFactory.create(organization=self.organization)
        member = MemberFactory.create(organization=self.organization)
        team_member_data = TeamMemberFactory.build(
            team=team, member=member, organization=self.organization
        )
        payload = {
            'team': team_member_data.team.id,
            'member': team_member_data.member.id,
            'role': team_member_data.role,
        }
        inactive_member = MemberFactory.create(
            organization=self.organization,
            is_active=False,
        )
        self.client.force_authenticate(member=inactive_member)
        response = self.client.post(self.list_url, data=payload)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_update_team_member(self):
        """Test updating a team member with an inactive member."""
        team_member = TeamMemberFactory.create(organization=self.organization)
        new_role = TeamMemberRoleChoices.ADMIN
        payload = {
            'role': new_role,
        }
        inactive_member = MemberFactory.create(
            organization=self.organization,
            is_active=False,
        )
        self.client.force_authenticate(member=inactive_member)
        response = self.client.put(
            reverse(self.detail_url_name, args=[team_member.id]), data=payload
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_delete_team_member(self):
        """Test deleting a team member with an inactive member."""
        team_member = TeamMemberFactory.create(organization=self.organization)
        inactive_member = MemberFactory.create(
            organization=self.organization,
            is_active=False,
        )
        self.client.force_authenticate(member=inactive_member)
        response = self.client.delete(
            reverse(self.detail_url_name, args=[team_member.id])
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
