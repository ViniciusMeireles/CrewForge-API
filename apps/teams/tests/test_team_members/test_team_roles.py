from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.choices import TeamMemberRoleChoices as TeamRole
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory

ALL_ROLES = set(TeamRole.values)
ADMIN_ROLES = {TeamRole.MANAGER, TeamRole.MEMBER}

OK = http_status.HTTP_200_OK
CREATED = http_status.HTTP_201_CREATED
NO_CONTENT = http_status.HTTP_204_NO_CONTENT
BAD_REQUEST = http_status.HTTP_400_BAD_REQUEST
FORBIDDEN = http_status.HTTP_403_FORBIDDEN


class TeamRolesTestMixin(APITestCaseMixin):
    def setUp(self):
        self.organization = self.new_account()
        self.team = TeamFactory(organization=self.organization)
        self.list_url = reverse('teams:team_members-list')

    def detail_url(self, team_member):
        return reverse('teams:team_members-detail', args=[team_member.pk])

    def org_member(self, role=MemberRoleChoices.MEMBER, **kwargs):
        return MemberFactory(organization=self.organization, role=role, **kwargs)

    def team_member(self, team_role=TeamRole.MEMBER, org_role=MemberRoleChoices.MEMBER):
        return TeamMemberFactory(
            team=self.team, member=self.org_member(org_role), role=team_role
        )

    def login_team_member(self, team_role, org_role=MemberRoleChoices.MEMBER):
        team_member = self.team_member(team_role, org_role)
        self.client.force_authenticate(member=team_member.member)
        return team_member


class AssignableTeamRolesTestCase(TeamRolesTestMixin, APITestCase):
    def test_organization_managers_assign_every_role(self):
        for org_role in (
            MemberRoleChoices.OWNER,
            MemberRoleChoices.ADMIN,
            MemberRoleChoices.MANAGER,
        ):
            with self.subTest(org_role=org_role):
                member = self.org_member(org_role)
                self.assertEqual(
                    set(TeamRole.assignable_by(member, self.team)), ALL_ROLES
                )
                self.assertEqual(set(TeamRole.assignable_by(member, None)), ALL_ROLES)
                self.assertTrue(self.team.can_manage_members(member))

    def test_team_roles_of_organization_members(self):
        expected = {
            TeamRole.OWNER: ALL_ROLES,
            TeamRole.ADMIN: ADMIN_ROLES,
            TeamRole.MANAGER: set(),
            TeamRole.MEMBER: set(),
        }
        for team_role, roles in expected.items():
            with self.subTest(team_role=team_role):
                member = self.team_member(team_role).member
                self.assertEqual(set(TeamRole.assignable_by(member, self.team)), roles)
                self.assertEqual(TeamRole.assignable_by(member, None), [])
                self.assertEqual(self.team.can_manage_members(member), bool(roles))

    def test_outsiders_and_removed_members_assign_nothing(self):
        outsider = self.org_member()
        removed = TeamMemberFactory(
            team=self.team,
            member=self.org_member(),
            role=TeamRole.OWNER,
            is_active=False,
        )
        for member in (outsider, removed.member, None):
            with self.subTest(member=member):
                self.assertEqual(TeamRole.assignable_by(member, self.team), [])


class TeamMemberWriteRulesTestCase(TeamRolesTestMixin, APITestCase):
    def _add(self, role, member=None):
        member = member or self.org_member()
        return self.client.post(
            self.list_url,
            {'team': self.team.pk, 'member': member.pk, 'role': role},
            format='json',
        )

    def _set_role(self, team_member, role):
        return self.client.put(
            self.detail_url(team_member), {'role': role}, format='json'
        )

    def test_plain_member_cannot_promote_themselves(self):
        own = self.login_team_member(TeamRole.MEMBER)
        self.assertEqual(self._set_role(own, TeamRole.OWNER).status_code, FORBIDDEN)
        own.refresh_from_db()
        self.assertEqual(own.role, TeamRole.MEMBER)

    def test_owner_cannot_change_own_role(self):
        self.team_member(TeamRole.OWNER)
        own = self.login_team_member(TeamRole.OWNER)
        self.assertEqual(self._set_role(own, TeamRole.MEMBER).status_code, FORBIDDEN)

    def test_plain_and_manager_members_cannot_add_or_edit(self):
        target = self.team_member(TeamRole.MEMBER)
        for team_role in (TeamRole.MEMBER, TeamRole.MANAGER):
            with self.subTest(team_role=team_role):
                self.login_team_member(team_role)
                self.assertEqual(self._add(TeamRole.MEMBER).status_code, BAD_REQUEST)
                self.assertEqual(
                    self._set_role(target, TeamRole.MANAGER).status_code, FORBIDDEN
                )
                response = self.client.delete(self.detail_url(target))
                self.assertEqual(response.status_code, FORBIDDEN)

    def test_team_owner_manages_every_role(self):
        self.login_team_member(TeamRole.OWNER)
        self.assertEqual(self._add(TeamRole.OWNER).status_code, CREATED)
        admin = self.team_member(TeamRole.ADMIN)
        self.assertEqual(self._set_role(admin, TeamRole.MEMBER).status_code, OK)
        self.assertEqual(
            self.client.delete(self.detail_url(admin)).status_code, NO_CONTENT
        )

    def test_team_admin_manages_managers_and_members_only(self):
        self.login_team_member(TeamRole.ADMIN)
        self.assertEqual(self._add(TeamRole.MANAGER).status_code, CREATED)
        response = self._add(TeamRole.OWNER)
        self.assertEqual(response.status_code, BAD_REQUEST)
        self.assertIn('role', response.data['error']['details'])
        self.assertEqual(self._add(TeamRole.ADMIN).status_code, BAD_REQUEST)

        member = self.team_member(TeamRole.MEMBER)
        self.assertEqual(self._set_role(member, TeamRole.MANAGER).status_code, OK)
        self.assertEqual(
            self._set_role(member, TeamRole.ADMIN).status_code, BAD_REQUEST
        )
        for team_role in (TeamRole.OWNER, TeamRole.ADMIN):
            with self.subTest(target=team_role):
                target = self.team_member(team_role)
                self.assertEqual(
                    self._set_role(target, TeamRole.MEMBER).status_code, FORBIDDEN
                )
                response = self.client.delete(self.detail_url(target))
                self.assertEqual(response.status_code, FORBIDDEN)
        self.assertEqual(
            self.client.delete(self.detail_url(member)).status_code, NO_CONTENT
        )

    def test_organization_manager_outside_the_team_manages_it(self):
        self.client.force_authenticate(
            member=self.org_member(MemberRoleChoices.MANAGER)
        )
        owner = self.team_member(TeamRole.OWNER)
        self.team_member(TeamRole.OWNER)
        self.assertEqual(self._add(TeamRole.OWNER).status_code, CREATED)
        self.assertEqual(self._set_role(owner, TeamRole.ADMIN).status_code, OK)

    def test_any_member_can_leave_the_team(self):
        own = self.login_team_member(TeamRole.MEMBER)
        self.assertEqual(
            self.client.delete(self.detail_url(own)).status_code, NO_CONTENT
        )
        own.refresh_from_db()
        self.assertFalse(own.is_active)

    def test_readding_a_removed_member_requires_managing_the_team(self):
        removed = TeamMemberFactory(
            team=self.team, member=self.org_member(), is_active=False
        )
        self.login_team_member(TeamRole.MEMBER)
        response = self._add(TeamRole.MEMBER, member=removed.member)
        self.assertEqual(response.status_code, BAD_REQUEST)
        removed.refresh_from_db()
        self.assertFalse(removed.is_active)

        self.client.force_authenticate(member=self.organization.owner)
        self.assertEqual(
            self._add(TeamRole.MEMBER, member=removed.member).status_code, CREATED
        )
        removed.refresh_from_db()
        self.assertTrue(removed.is_active)


class ReaddDefaultRoleTestCase(TeamRolesTestMixin, APITestCase):
    def test_readded_member_without_role_becomes_member(self):
        removed = TeamMemberFactory(
            team=self.team,
            member=self.org_member(),
            role=TeamRole.OWNER,
            is_active=False,
        )
        response = self.client.post(
            self.list_url,
            {'team': self.team.pk, 'member': removed.member_id},
            format='json',
        )
        self.assertEqual(response.status_code, CREATED)
        removed.refresh_from_db()
        self.assertTrue(removed.is_active)
        self.assertEqual(removed.role, TeamRole.MEMBER)


class LastOwnerTestCase(TeamRolesTestMixin, APITestCase):
    def test_last_owner_cannot_leave_or_be_removed(self):
        owner = self.team_member(TeamRole.OWNER)
        for login in (owner.member, self.organization.owner):
            with self.subTest(login=login):
                self.client.force_authenticate(member=login)
                response = self.client.delete(self.detail_url(owner))
                self.assertEqual(response.status_code, BAD_REQUEST)
                self.assertIn('role', response.data['error']['details'])
        owner.refresh_from_db()
        self.assertTrue(owner.is_active)

    def test_last_owner_cannot_be_demoted(self):
        owner = self.team_member(TeamRole.OWNER)
        response = self.client.put(
            self.detail_url(owner), {'role': TeamRole.ADMIN}, format='json'
        )
        self.assertEqual(response.status_code, BAD_REQUEST)
        self.assertIn('role', response.data['error']['details'])

    def test_owner_can_go_when_another_owner_remains(self):
        owner = self.team_member(TeamRole.OWNER)
        self.team_member(TeamRole.OWNER)
        response = self.client.put(
            self.detail_url(owner), {'role': TeamRole.ADMIN}, format='json'
        )
        self.assertEqual(response.status_code, OK)
        other_owner = self.team_member(TeamRole.OWNER)
        self.assertEqual(
            self.client.delete(self.detail_url(other_owner)).status_code, NO_CONTENT
        )

    def test_inactive_organization_owner_does_not_count(self):
        owner = self.team_member(TeamRole.OWNER)
        TeamMemberFactory(
            team=self.team,
            member=self.org_member(is_active=False),
            role=TeamRole.OWNER,
        )
        response = self.client.delete(self.detail_url(owner))
        self.assertEqual(response.status_code, BAD_REQUEST)


class TeamMemberReadDataTestCase(TeamRolesTestMixin, APITestCase):
    def test_member_detail_and_role_label(self):
        team_member = self.team_member(TeamRole.ADMIN, MemberRoleChoices.MANAGER)
        response = self.client.get(self.list_url, {'team': self.team.pk})
        self.assertEqual(response.status_code, OK)
        result = response.data['results'][0]
        member = team_member.member
        self.assertEqual(result['role_label'], 'Admin')
        self.assertEqual(
            result['member_detail'],
            {
                'id': member.pk,
                'full_name': member.user.full_name,
                'email': member.user.email,
                'nickname': member.nickname,
                'role': MemberRoleChoices.MANAGER,
                'role_label': 'Manager',
            },
        )

    def _count_list_queries(self) -> int:
        with CaptureQueriesContext(connection) as captured:
            self.client.get(self.list_url, {'team': self.team.pk})
        return len(captured)

    def test_list_query_count_does_not_grow_per_row(self):
        self.team_member()
        one_row = self._count_list_queries()
        for _ in range(3):
            self.team_member()
        self.assertEqual(self._count_list_queries(), one_row)


class TeamMemberFormOptionsTestCase(TeamRolesTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.create_url = reverse('teams:team_members-form-options-create')
        self.update_url = reverse('teams:team_members-form-options-update')

    def _roles(self, url, **params):
        response = self.client.get(url, {'role': '', **params})
        self.assertEqual(response.status_code, OK)
        return {option['value'] for option in response.data['role']}

    def _members(self, **params):
        response = self.client.get(self.create_url, {'member': '', **params})
        self.assertEqual(response.status_code, OK)
        return {option['value'] for option in response.data['member']['results']}

    def test_roles_per_requester_in_the_team(self):
        expected = {
            TeamRole.OWNER: ALL_ROLES,
            TeamRole.ADMIN: ADMIN_ROLES,
            TeamRole.MANAGER: set(),
            TeamRole.MEMBER: set(),
        }
        for team_role, roles in expected.items():
            with self.subTest(team_role=team_role):
                self.login_team_member(team_role)
                for url in (self.create_url, self.update_url):
                    self.assertEqual(self._roles(url, team_id=self.team.pk), roles)

    def test_roles_without_or_with_invalid_team(self):
        other_team = TeamFactory(organization=OrganizationFactory())
        self.login_team_member(TeamRole.OWNER)
        for params in ({}, {'team_id': other_team.pk}, {'team_id': 'abc'}):
            with self.subTest(params=params):
                self.assertEqual(self._roles(self.create_url, **params), set())
        self.client.force_authenticate(member=self.organization.owner)
        self.assertEqual(self._roles(self.create_url), ALL_ROLES)

    def test_malformed_team_id_is_ignored(self):
        self.client.force_authenticate(member=self.organization.owner)
        for value in ('²', '١٢', '-1', '0', ' 5', '99999999999999999999999'):
            with self.subTest(team_id=value):
                self.assertEqual(self._roles(self.create_url, team_id=value), ALL_ROLES)

    def test_members_exclude_active_team_members(self):
        active = self.team_member()
        removed = TeamMemberFactory(
            team=self.team, member=self.org_member(), is_active=False
        )
        outsider = self.org_member()
        values = self._members(team_id=self.team.pk)
        self.assertNotIn(active.member_id, values)
        self.assertIn(removed.member_id, values)
        self.assertIn(outsider.pk, values)
        self.assertIn(active.member_id, self._members())

    def test_member_search_with_team_context(self):
        outsider = self.org_member()
        name = outsider.user.full_name.split()[0]
        values = self._members(team_id=self.team.pk, member=name)
        self.assertIn(outsider.pk, values)

    def test_filter_options_do_not_document_team_id(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)
        operation = schema['paths']['/api/teams/team-members/filter-options/']['get']
        names = {parameter['name'] for parameter in operation.get('parameters', [])}
        self.assertNotIn('team_id', names)
