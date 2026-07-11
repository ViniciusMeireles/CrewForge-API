from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.factories.teams import TeamFactory


class TeamPermissionTestCase(APITestCaseMixin, APITestCase):
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

    def _create_team(self):
        return TeamFactory(organization=self.organization)

    # --- Unauthenticated ---

    def test_not_authenticated_list(self):
        self.client.logout()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_retrieve(self):
        team = self._create_team()
        self.client.logout()
        url = self._detail_url(team)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_create(self):
        self.client.logout()
        payload = self._team_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_update(self):
        team = self._create_team()
        self.client.logout()
        url = self._detail_url(team)
        payload = self._team_payload()
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_delete(self):
        team = self._create_team()
        self.client.logout()
        url = self._detail_url(team)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    # --- Inactive member ---

    def test_not_active_member_list(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_retrieve(self):
        team = self._create_team()
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        url = self._detail_url(team)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_create(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        payload = self._team_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_update(self):
        team = self._create_team()
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        url = self._detail_url(team)
        payload = self._team_payload()
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_delete(self):
        team = self._create_team()
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        url = self._detail_url(team)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- Owner ---

    def test_owner_can_create(self):
        payload = self._team_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_owner_can_update(self):
        team = self._create_team()
        payload = self._team_payload()
        url = self._detail_url(team)
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_can_delete(self):
        team = self._create_team()
        url = self._detail_url(team)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    # --- Admin ---

    def test_admin_can_create(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        payload = self._team_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_admin_can_update(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        team = self._create_team()
        payload = self._team_payload()
        url = self._detail_url(team)
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_delete(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        team = self._create_team()
        url = self._detail_url(team)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    # --- Manager ---

    def test_manager_can_create(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        payload = self._team_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_manager_can_update(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        team = self._create_team()
        payload = self._team_payload()
        url = self._detail_url(team)
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_manager_can_delete(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        team = self._create_team()
        url = self._detail_url(team)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    # --- Member ---

    def test_member_cannot_create(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        payload = self._team_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_member_cannot_update(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        team = self._create_team()
        payload = self._team_payload()
        url = self._detail_url(team)
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_member_cannot_delete(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        team = self._create_team()
        url = self._detail_url(team)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- All roles can read ---

    def test_owner_can_retrieve(self):
        team = self._create_team()
        url = self._detail_url(team)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_retrieve(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        team = self._create_team()
        url = self._detail_url(team)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_manager_can_retrieve(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        team = self._create_team()
        url = self._detail_url(team)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_member_can_retrieve(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        team = self._create_team()
        url = self._detail_url(team)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Choices ---

    def test_not_authenticated_choices(self):
        self.client.logout()
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_active_member_choices(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- Owner list ---

    def test_owner_can_list(self):
        self._create_team()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    # --- Member list ---

    def test_member_can_list(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Cross-org ---

    def test_cross_org_member_retrieve_returns_404(self):
        other_org = OrganizationFactory()
        other_member = other_org.owner
        team = self._create_team()
        self.client.force_authenticate(member=other_member)
        url = self._detail_url(team)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_member_create_returns_201(self):
        other_org = OrganizationFactory()
        other_member = other_org.owner
        self.client.force_authenticate(member=other_member)
        payload = self._team_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['organization'], other_org.id)

    def test_cross_org_member_update_returns_404(self):
        other_org = OrganizationFactory()
        other_admin = MemberFactory(
            organization=other_org, role=MemberRoleChoices.ADMIN
        )
        team = self._create_team()
        self.client.force_authenticate(member=other_admin)
        url = self._detail_url(team)
        payload = self._team_payload()
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_member_delete_returns_404(self):
        other_org = OrganizationFactory()
        other_admin = MemberFactory(
            organization=other_org, role=MemberRoleChoices.ADMIN
        )
        team = self._create_team()
        self.client.force_authenticate(member=other_admin)
        url = self._detail_url(team)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_member_list_returns_empty(self):
        self._create_team()
        other_org = OrganizationFactory()
        other_member = other_org.owner
        self.client.force_authenticate(member=other_member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
