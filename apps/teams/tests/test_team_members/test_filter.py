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


class TeamMemberOrderingTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.team = TeamFactory(organization=self.organization)
        self.list_url = reverse('teams:team_members-list')
        self.rows = {}
        for role, first_name, email in (
            (TeamMemberRoleChoices.MEMBER, 'Ana', 'zoe@example.com'),
            (TeamMemberRoleChoices.OWNER, 'Carla', 'bia@example.com'),
            (TeamMemberRoleChoices.MANAGER, 'Bruno', 'xavier@example.com'),
            (TeamMemberRoleChoices.ADMIN, 'Daniel', 'alice@example.com'),
        ):
            member = MemberFactory(organization=self.organization)
            member.user.first_name = first_name
            member.user.last_name = 'Silva'
            member.user.email = email
            member.user.save()
            self.rows[role] = TeamMemberFactory(
                team=self.team, member=member, role=role
            )

    def _ordered(self, order_by):
        response = self.client.get(
            self.list_url, {'team': self.team.pk, 'order_by': order_by}
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        return response.data['results']

    def test_order_by_member_name(self):
        names = [r['member_detail']['full_name'] for r in self._ordered('member_name')]
        self.assertEqual(names, sorted(names))
        names = [r['member_detail']['full_name'] for r in self._ordered('-member_name')]
        self.assertEqual(names, sorted(names, reverse=True))

    def test_order_by_member_email(self):
        emails = [r['member_detail']['email'] for r in self._ordered('member_email')]
        self.assertEqual(emails, sorted(emails))
        emails = [r['member_detail']['email'] for r in self._ordered('-member_email')]
        self.assertEqual(emails, sorted(emails, reverse=True))

    def test_order_by_role_follows_hierarchy(self):
        hierarchy = [
            TeamMemberRoleChoices.OWNER,
            TeamMemberRoleChoices.ADMIN,
            TeamMemberRoleChoices.MANAGER,
            TeamMemberRoleChoices.MEMBER,
        ]
        self.assertEqual([r['role'] for r in self._ordered('role')], hierarchy)
        self.assertEqual([r['role'] for r in self._ordered('-role')], hierarchy[::-1])

    def test_order_by_created_at(self):
        ids = [r['id'] for r in self._ordered('created_at')]
        expected = [
            tm.pk for tm in sorted(self.rows.values(), key=lambda tm: tm.created_at)
        ]
        self.assertEqual(ids, expected)

    def test_pages_are_stable_when_ordered_values_repeat(self):
        for _ in range(4):
            TeamMemberFactory(team=self.team, role=TeamMemberRoleChoices.MEMBER)
        seen = []
        for page in (1, 2, 3, 4):
            response = self.client.get(
                self.list_url,
                {
                    'team': self.team.pk,
                    'order_by': 'role',
                    'page_size': 2,
                    'page': page,
                },
            )
            seen.extend(r['id'] for r in response.data['results'])
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(len(seen), 8)

    def test_filter_options_list_ordering_values(self):
        response = self.client.get(
            reverse('teams:team_members-filter-options'), {'order_by': ''}
        )
        values = [option['value'] for option in response.data['order_by']]
        for value in ('member_name', 'member_email', 'role', 'created_at'):
            with self.subTest(value=value):
                self.assertIn(value, values)
                self.assertIn(f'-{value}', values)
