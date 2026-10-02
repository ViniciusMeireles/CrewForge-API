from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin, FilterOptionsTestMixin
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.teams import TeamFactory

OK = http_status.HTTP_200_OK
UNAUTHORIZED = http_status.HTTP_401_UNAUTHORIZED
FORBIDDEN = http_status.HTTP_403_FORBIDDEN

RESOURCES = {
    'teams': {'organization', 'order_by'},
    'team_members': {'team', 'member', 'role', 'role__in', 'order_by'},
}


def _status(status):
    return dict.fromkeys(RESOURCES, status)


class TeamsFilterOptionsTestMixin(FilterOptionsTestMixin):
    filter_options_namespace = 'teams'
    expected_status = {
        'owner': _status(OK),
        'member': _status(OK),
        'inactive': _status(FORBIDDEN),
        'no_session': _status(FORBIDDEN),
        'anonymous': _status(UNAUTHORIZED),
    }


class FilterOptionsPermissionTestCase(
    TeamsFilterOptionsTestMixin, APITestCaseMixin, APITestCase
):
    def setUp(self):
        self.organization = self.new_account()

    def test_owner(self):
        self.assert_expected_status('owner')
        for resource, fields in RESOURCES.items():
            with self.subTest(resource=resource):
                response = self.client.get(self.filter_options_url(resource))
                self.assertEqual(set(response.data), fields)

    def test_member_role(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        self.assert_expected_status('member')

    def test_inactive_member(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        self.assert_expected_status('inactive')

    def test_without_organization_session(self):
        self.client.logout()
        self.client.force_authenticate(user=self.organization.owner.user)
        self.assert_expected_status('no_session')

    def test_not_authenticated(self):
        self.client.logout()
        self.assert_expected_status('anonymous')


class FilterOptionsContentTestCase(
    TeamsFilterOptionsTestMixin, APITestCaseMixin, APITestCase
):
    def setUp(self):
        self.organization = self.new_account()
        self.other_organization = OrganizationFactory()

    def test_team_members_scoped_to_organization_and_active(self):
        team = TeamFactory(organization=self.organization)
        TeamFactory(organization=self.organization, is_active=False)
        TeamFactory(organization=self.other_organization)
        member = MemberFactory(organization=self.organization)
        MemberFactory(organization=self.organization, is_active=False)
        MemberFactory(organization=self.other_organization)
        response = self.client.get(self.filter_options_url('team_members'))
        self.assertEqual(self.option_values(response, 'team'), {team.pk})
        self.assertEqual(
            self.option_values(response, 'member'),
            {self.organization.owner.pk, member.pk},
        )

    def test_team_members_role_choices(self):
        response = self.client.get(
            self.filter_options_url('team_members'), {'role': ''}
        )
        self.assertEqual(set(response.data), {'role'})
        self.assertEqual(
            self.option_values(response, 'role'), set(TeamMemberRoleChoices.values)
        )

    def test_team_search(self):
        team = TeamFactory(organization=self.organization, name='Gestão Ágil')
        TeamFactory(organization=self.organization, name='Outro')
        response = self.client.get(
            self.filter_options_url('team_members'), {'team': 'gestao'}
        )
        self.assertEqual(self.option_values(response, 'team'), {team.pk})

    def test_teams_organization_scoped(self):
        response = self.client.get(self.filter_options_url('teams'))
        self.assertEqual(
            self.option_values(response, 'organization'), {self.organization.pk}
        )
