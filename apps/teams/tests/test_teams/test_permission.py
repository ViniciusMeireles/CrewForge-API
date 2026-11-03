from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.accounts.tests.permission_matrix import (
    ADMIN,
    ANONYMOUS,
    INACTIVE,
    MANAGER,
    MEMBER,
    OTHER_ORGANIZATION,
    OWNER,
    Action,
    PermissionMatrixMixin,
)
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory

LIST = reverse('teams:teams-list')


def _detail(case):
    team = TeamFactory(organization=case.organization)
    return reverse('teams:teams-detail', args=[team.pk])


def _payload(case):
    team = TeamFactory.build()
    return {'name': team.name, 'slug': team.slug, 'description': team.description}


class TeamPermissionMatrixTestCase(
    PermissionMatrixMixin, APITestCaseMixin, APITestCase
):
    inactive_role = MemberRoleChoices.MEMBER
    actions = {
        'list': Action('get', lambda case: LIST),
        'retrieve': Action('get', _detail),
        'create': Action('post', lambda case: LIST, _payload),
        'update': Action('put', _detail, _payload),
        'delete': Action('delete', _detail),
    }
    matrix = {
        ANONYMOUS: {
            'list': 401,
            'retrieve': 401,
            'create': 401,
            'update': 401,
            'delete': 401,
        },
        INACTIVE: {
            'list': 403,
            'retrieve': 403,
            'create': 403,
            'update': 403,
            'delete': 403,
        },
        OWNER: {'retrieve': 200, 'create': 201, 'update': 200, 'delete': 204},
        ADMIN: {'retrieve': 200, 'create': 201, 'update': 200, 'delete': 204},
        MANAGER: {'retrieve': 200, 'create': 201, 'update': 200, 'delete': 204},
        MEMBER: {
            'list': 200,
            'retrieve': 200,
            'create': 403,
            'update': 403,
            'delete': 403,
        },
        OTHER_ORGANIZATION: {'retrieve': 404, 'update': 404, 'delete': 404},
    }

    def setUp(self):
        self.organization = OrganizationFactory()


class TeamPermissionTestCase(APITestCaseMixin, APITestCase):
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

    def _create_team(self):
        return TeamFactory(organization=self.organization)

    def _team_leader(self, team, role):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        TeamMemberFactory(
            organization=self.organization, team=team, member=member, role=role
        )
        self.client.force_authenticate(member=member)

    def test_team_owner_member_cannot_update(self):
        team = self._create_team()
        self._team_leader(team, TeamMemberRoleChoices.OWNER)
        payload = self._team_payload()
        response = self.client.put(self._detail_url(team), data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_team_admin_member_cannot_partial_update(self):
        team = self._create_team()
        self._team_leader(team, TeamMemberRoleChoices.ADMIN)
        response = self.client.patch(
            self._detail_url(team), data={'name': 'Renamed'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_team_owner_member_cannot_delete(self):
        team = self._create_team()
        self._team_leader(team, TeamMemberRoleChoices.OWNER)
        response = self.client.delete(self._detail_url(team))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        team.refresh_from_db()
        self.assertTrue(team.is_active)

    def test_team_owner_member_can_retrieve(self):
        team = self._create_team()
        self._team_leader(team, TeamMemberRoleChoices.OWNER)
        response = self.client.get(self._detail_url(team))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_can_list(self):
        self._create_team()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_cross_org_member_create_returns_201(self):
        other_org = OrganizationFactory()
        other_member = other_org.owner
        self.client.force_authenticate(member=other_member)
        payload = self._team_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['organization'], other_org.id)

    def test_cross_org_member_list_returns_empty(self):
        self._create_team()
        other_org = OrganizationFactory()
        other_member = other_org.owner
        self.client.force_authenticate(member=other_member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
