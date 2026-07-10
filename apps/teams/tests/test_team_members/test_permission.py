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


class TeamMemberPermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('teams:team_members-list')
        self.choices_url = reverse('teams:team_members-choices')

    def _detail_url(self, tm):
        return reverse('teams:team_members-detail', args=[tm.id])

    def _create_tm(self):
        return TeamMemberFactory(organization=self.organization)

    def _create_role_member(self, role=MemberRoleChoices.MEMBER):
        return MemberFactory(organization=self.organization, role=role)

    # --- Unauthenticated ---

    def test_not_authenticated_list(self):
        self.client.logout()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_retrieve(self):
        tm = self._create_tm()
        self.client.logout()
        response = self.client.get(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_create(self):
        self.client.logout()
        response = self.client.post(self.list_url, data={}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_update(self):
        tm = self._create_tm()
        self.client.logout()
        response = self.client.put(
            self._detail_url(tm), data={'role': 'admin'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_delete(self):
        tm = self._create_tm()
        self.client.logout()
        response = self.client.delete(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_choices(self):
        self.client.logout()
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    # --- Inactive member ---

    def test_not_active_member_list(self):
        inactive = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=inactive)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_retrieve(self):
        tm = self._create_tm()
        inactive = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=inactive)
        response = self.client.get(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_create(self):
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {'team': team.id, 'member': member.id}
        inactive = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=inactive)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_update(self):
        tm = self._create_tm()
        inactive = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=inactive)
        response = self.client.put(
            self._detail_url(tm), data={'role': 'admin'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_delete(self):
        tm = self._create_tm()
        inactive = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=inactive)
        response = self.client.delete(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_choices(self):
        inactive = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=inactive)
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- Owner ---

    def test_owner_can_create(self):
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {'team': team.id, 'member': member.id}
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_owner_can_update(self):
        tm = self._create_tm()
        response = self.client.put(
            self._detail_url(tm),
            data={'role': TeamMemberRoleChoices.ADMIN},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_can_delete(self):
        tm = self._create_tm()
        response = self.client.delete(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    # --- Admin ---

    def test_admin_can_create(self):
        admin = self._create_role_member(role=MemberRoleChoices.ADMIN)
        self.client.force_authenticate(member=admin)
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {'team': team.id, 'member': member.id}
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_admin_can_update(self):
        admin = self._create_role_member(role=MemberRoleChoices.ADMIN)
        self.client.force_authenticate(member=admin)
        tm = self._create_tm()
        response = self.client.put(
            self._detail_url(tm),
            data={'role': TeamMemberRoleChoices.ADMIN},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_delete(self):
        admin = self._create_role_member(role=MemberRoleChoices.ADMIN)
        self.client.force_authenticate(member=admin)
        tm = self._create_tm()
        response = self.client.delete(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    # --- Manager ---

    def test_manager_can_create(self):
        manager = self._create_role_member(role=MemberRoleChoices.MANAGER)
        self.client.force_authenticate(member=manager)
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {'team': team.id, 'member': member.id}
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_manager_can_update(self):
        manager = self._create_role_member(role=MemberRoleChoices.MANAGER)
        self.client.force_authenticate(member=manager)
        tm = self._create_tm()
        response = self.client.put(
            self._detail_url(tm),
            data={'role': TeamMemberRoleChoices.ADMIN},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_manager_can_delete(self):
        manager = self._create_role_member(role=MemberRoleChoices.MANAGER)
        self.client.force_authenticate(member=manager)
        tm = self._create_tm()
        response = self.client.delete(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_manager_cannot_create_team_member(self):
        manager = self._create_role_member(role=MemberRoleChoices.MANAGER)
        self.client.force_authenticate(member=manager)
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {'team': team.id, 'member': member.id}
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    # --- Member ---

    def test_member_cannot_create(self):
        member_role = self._create_role_member(role=MemberRoleChoices.MEMBER)
        self.client.force_authenticate(member=member_role)
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {'team': team.id, 'member': member.id}
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_member_cannot_update(self):
        member_role = self._create_role_member(role=MemberRoleChoices.MEMBER)
        self.client.force_authenticate(member=member_role)
        tm = self._create_tm()
        response = self.client.put(
            self._detail_url(tm),
            data={'role': TeamMemberRoleChoices.ADMIN},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_member_cannot_delete(self):
        member_role = self._create_role_member(role=MemberRoleChoices.MEMBER)
        self.client.force_authenticate(member=member_role)
        tm = self._create_tm()
        response = self.client.delete(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- All roles can read ---

    def test_owner_can_retrieve(self):
        tm = self._create_tm()
        response = self.client.get(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_retrieve(self):
        admin = self._create_role_member(role=MemberRoleChoices.ADMIN)
        self.client.force_authenticate(member=admin)
        tm = self._create_tm()
        response = self.client.get(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_manager_can_retrieve(self):
        manager = self._create_role_member(role=MemberRoleChoices.MANAGER)
        self.client.force_authenticate(member=manager)
        tm = self._create_tm()
        response = self.client.get(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_member_can_retrieve(self):
        member_role = self._create_role_member(role=MemberRoleChoices.MEMBER)
        self.client.force_authenticate(member=member_role)
        tm = self._create_tm()
        response = self.client.get(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Cross-org ---

    def test_cross_org_member_retrieve_returns_404(self):
        other_org = OrganizationFactory()
        other_member = other_org.owner
        tm = self._create_tm()
        self.client.force_authenticate(member=other_member)
        response = self.client.get(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_member_create_returns_400(self):
        other_org = OrganizationFactory()
        other_owner = other_org.owner
        self.client.force_authenticate(member=other_owner)
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {'team': team.id, 'member': member.id}
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_cross_org_member_update_returns_404(self):
        other_org = OrganizationFactory()
        other_admin = MemberFactory(
            organization=other_org, role=MemberRoleChoices.ADMIN
        )
        tm = self._create_tm()
        self.client.force_authenticate(member=other_admin)
        response = self.client.put(
            self._detail_url(tm),
            data={'role': TeamMemberRoleChoices.ADMIN},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_member_delete_returns_404(self):
        other_org = OrganizationFactory()
        other_admin = MemberFactory(
            organization=other_org, role=MemberRoleChoices.ADMIN
        )
        tm = self._create_tm()
        self.client.force_authenticate(member=other_admin)
        response = self.client.delete(self._detail_url(tm))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_member_list_returns_empty(self):
        other_org = OrganizationFactory()
        other_member = other_org.owner
        TeamMemberFactory(organization=self.organization)
        self.client.force_authenticate(member=other_member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_cross_org_member_choices_returns_empty(self):
        other_org = OrganizationFactory()
        other_member = other_org.owner
        TeamMemberFactory(organization=self.organization)
        self.client.force_authenticate(member=other_member)
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
