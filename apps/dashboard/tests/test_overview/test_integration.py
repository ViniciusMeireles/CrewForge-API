from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.models.member import Member
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory


class OverviewIntegrationTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.url = reverse('dashboard:overview')
        self.organization = self.new_account()
        self.member = self.organization.owner

    def _get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        return response.data

    def test_payload_shape(self):
        data = self._get()
        self.assertEqual(
            set(data.keys()),
            {
                'generated_at',
                'member',
                'members',
                'teams',
                'invitations',
                'received_invitations',
            },
        )
        self.assertEqual(
            set(data['member'].keys()),
            {'id', 'role', 'role_label', 'created_at', 'joined_at'},
        )
        self.assertIsInstance(data['generated_at'], str)
        self.assertIsInstance(data['member']['role_label'], str)
        self.assertIn(data['member']['role'], MemberRoleChoices.values)
        self.assertEqual(
            set(data['members'].keys()),
            {'total', 'by_role', 'recent'},
        )
        self.assertEqual(
            set(data['teams'].keys()),
            {'total', 'mine_count', 'mine'},
        )
        self.assertEqual(
            set(data['invitations'].keys()),
            {'pending', 'expiring_soon'},
        )
        self.assertEqual(data['received_invitations'], {'pending': 0})
        self.assertIsInstance(data['members']['total'], int)

    def test_by_role_four_rows_zeros_and_sum(self):
        for _ in range(3):
            MemberFactory(
                organization=self.organization,
                role=MemberRoleChoices.MEMBER,
            )
        data = self._get()
        by_role = data['members']['by_role']
        self.assertEqual(
            [row['role'] for row in by_role],
            ['owner', 'admin', 'manager', 'member'],
        )
        self.assertEqual([row['count'] for row in by_role], [1, 0, 0, 3])
        self.assertTrue(all(row['role_label'] for row in by_role))
        self.assertEqual(data['members']['total'], 4)
        self.assertEqual(sum(row['count'] for row in by_role), 4)

    def test_recent_ordering_limit_and_fields(self):
        created = [
            MemberFactory(
                organization=self.organization,
                role=MemberRoleChoices.MEMBER,
            )
            for _ in range(7)
        ]
        data = self._get()
        recent = data['members']['recent']
        self.assertEqual(len(recent), 5)
        self.assertEqual(
            [row['id'] for row in recent],
            [m.id for m in reversed(created[-5:])],
        )
        expected_keys = {
            'id',
            'full_name',
            'email',
            'nickname',
            'role',
            'role_label',
            'created_at',
            'joined_at',
        }
        for row in recent:
            self.assertEqual(set(row.keys()), expected_keys)
            self.assertIsInstance(row['full_name'], str)
            self.assertIsInstance(row['email'], str)
            self.assertIn(row['role'], MemberRoleChoices.values)

    def test_readmitted_member_is_first_in_recent(self):
        removed = MemberFactory(organization=self.organization, is_active=False)
        MemberFactory(organization=self.organization)
        Member.objects.admit(
            user=removed.user,
            organization=self.organization,
            role=MemberRoleChoices.MEMBER,
        )
        recent = self._get()['members']['recent']
        self.assertEqual(recent[0]['id'], removed.pk)

    def test_teams_total_mine_count_ordering_and_limit(self):
        names = [
            'Zeta Team',
            'alpha Team',
            'Mike',
            'bravo',
            'Echo',
            'delta',
            'Foxtrot',
            'charlie',
        ]
        for name in names:
            team = TeamFactory(organization=self.organization, name=name)
            TeamMemberFactory(
                organization=self.organization,
                team=team,
                member=self.member,
            )
        data = self._get()
        self.assertEqual(data['teams']['total'], 8)
        self.assertEqual(data['teams']['mine_count'], 8)
        mine = data['teams']['mine']
        self.assertEqual(len(mine), 5)
        self.assertEqual(
            [row['name'] for row in mine],
            ['alpha Team', 'bravo', 'charlie', 'delta', 'Echo'],
        )

    def test_mine_member_count_excludes_inactive(self):
        team = TeamFactory(organization=self.organization)
        TeamMemberFactory(
            organization=self.organization,
            team=team,
            member=self.member,
        )
        TeamMemberFactory(
            organization=self.organization,
            team=team,
            member=MemberFactory(organization=self.organization),
        )
        TeamMemberFactory(
            organization=self.organization,
            team=team,
            member=MemberFactory(
                organization=self.organization,
                is_active=False,
            ),
        )
        TeamMemberFactory(
            organization=self.organization,
            team=team,
            member=MemberFactory(organization=self.organization),
            is_active=False,
        )
        data = self._get()
        mine = data['teams']['mine']
        self.assertEqual(data['teams']['mine_count'], 1)
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]['member_count'], 2)

    def test_mine_id_is_team_id_and_team_level_role(self):
        team = TeamFactory(organization=self.organization)
        TeamMemberFactory(
            organization=self.organization,
            team=team,
            member=self.member,
            role=TeamMemberRoleChoices.MANAGER,
        )
        data = self._get()
        mine = data['teams']['mine']
        self.assertEqual(mine[0]['id'], team.id)
        self.assertEqual(mine[0]['role'], TeamMemberRoleChoices.MANAGER)
        self.assertEqual(mine[0]['role_label'], 'Manager')
        self.assertEqual(mine[0]['slug'], team.slug)

    def test_expiring_soon_window_ordering_and_limit(self):
        now = timezone.now()
        in_window = []
        for days in (6, 3, 1, 5, 2, 4):
            in_window.append(
                InvitationFactory(
                    organization=self.organization,
                    role=MemberRoleChoices.MEMBER,
                    expired_at=now + timedelta(days=days),
                )
            )
        outside = InvitationFactory(
            organization=self.organization,
            expired_at=now + timedelta(days=10),
        )
        without_expiry = InvitationFactory(
            organization=self.organization,
            expired_at=None,
        )
        data = self._get()
        self.assertEqual(data['invitations']['pending'], 8)
        expiring = data['invitations']['expiring_soon']
        self.assertEqual(len(expiring), 5)
        expected = sorted(in_window, key=lambda i: i.expired_at)[:5]
        self.assertEqual(
            [row['id'] for row in expiring],
            [invitation.id for invitation in expected],
        )
        self.assertNotIn(outside.id, [row['id'] for row in expiring])
        self.assertNotIn(without_expiry.id, [row['id'] for row in expiring])
        expected_keys = {'id', 'email', 'role', 'role_label', 'expired_at'}
        for row in expiring:
            self.assertEqual(set(row.keys()), expected_keys)
