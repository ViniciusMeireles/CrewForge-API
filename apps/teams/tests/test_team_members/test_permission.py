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
    NO_SESSION,
    OTHER_ORGANIZATION,
    OWNER,
    Action,
    PermissionMatrixMixin,
)
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory

LIST = reverse('teams:team_members-list')
FORM_OPTIONS = reverse('teams:team_members-form-options-create')


def _detail(case):
    team_member = TeamMemberFactory(organization=case.organization)
    return reverse('teams:team_members-detail', args=[team_member.pk])


def _new_team_member(case):
    team = TeamFactory(organization=case.organization)
    member = MemberFactory(organization=case.organization)
    return {'team': team.pk, 'member': member.pk}


def _promote(case):
    return {'role': TeamMemberRoleChoices.ADMIN}


MANAGES = {'retrieve': 200, 'create': 201, 'update': 200, 'delete': 204}


class TeamMemberPermissionMatrixTestCase(
    PermissionMatrixMixin, APITestCaseMixin, APITestCase
):
    inactive_role = MemberRoleChoices.MEMBER
    actions = {
        'list': Action('get', lambda case: LIST),
        'retrieve': Action('get', _detail),
        'create': Action('post', lambda case: LIST, _new_team_member),
        'update': Action('put', _detail, _promote),
        'delete': Action('delete', _detail),
        'form_options': Action('get', lambda case: FORM_OPTIONS),
    }
    matrix = {
        ANONYMOUS: {
            'list': 401,
            'retrieve': 401,
            'create': 401,
            'update': 401,
            'delete': 401,
            'form_options': 401,
        },
        NO_SESSION: {'form_options': 403},
        INACTIVE: {
            'list': 403,
            'retrieve': 403,
            'create': 403,
            'update': 403,
            'delete': 403,
            'form_options': 403,
        },
        OWNER: MANAGES,
        ADMIN: MANAGES,
        MANAGER: MANAGES,
        MEMBER: {
            'retrieve': 200,
            'create': 400,
            'update': 403,
            'delete': 403,
            'form_options': 200,
        },
        OTHER_ORGANIZATION: {
            'retrieve': 404,
            'create': 400,
            'update': 404,
            'delete': 404,
        },
    }

    def setUp(self):
        self.organization = OrganizationFactory()


class TeamMemberPermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('teams:team_members-list')

    def _detail_url(self, tm):
        return reverse('teams:team_members-detail', args=[tm.id])

    def _create_tm(self):
        return TeamMemberFactory(organization=self.organization)

    def _create_role_member(self, role=MemberRoleChoices.MEMBER):
        return MemberFactory(organization=self.organization, role=role)

    def test_cross_org_member_list_returns_empty(self):
        other_org = OrganizationFactory()
        other_member = other_org.owner
        TeamMemberFactory(organization=self.organization)
        self.client.force_authenticate(member=other_member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def _form_options_urls(self):
        return (
            reverse('teams:team_members-form-options-create'),
            reverse('teams:team_members-form-options-update'),
        )

    def test_cross_org_form_options_only_session_organization(self):
        own_team = TeamFactory(organization=self.organization)
        other_org = OrganizationFactory()
        TeamFactory(organization=other_org)
        self.client.force_authenticate(member=other_org.owner)
        response = self.client.get(
            reverse('teams:team_members-form-options-create'), {'team': ''}
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        team_values = {r['value'] for r in response.data['team']['results']}
        self.assertNotIn(own_team.pk, team_values)
