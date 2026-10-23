from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.platform.tests.mixins import PlatformTestMixin
from apps.teams.factories.teams import TeamFactory


class PlatformOrganizationListTestCase(
    PlatformTestMixin, APITestCaseMixin, APITestCase
):
    def setUp(self):
        self.list_url = reverse('platform:organizations-list')
        self.acme = OrganizationFactory(name='Acme Inc')
        self.globex = OrganizationFactory(name='Globex Corp', suspended=True)
        self.deleted = OrganizationFactory(name='Gone Ltd')
        self.deleted.is_active = False
        self.deleted.save(update_fields=['is_active'])
        self.authenticate_staff()

    def names(self, **params):
        response = self.client.get(self.list_url, data=params)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        return {row['name'] for row in response.data['results']}

    def test_fields(self):
        response = self.client.get(self.list_url, data={'search': 'Acme'})
        row = response.data['results'][0]
        self.assertEqual(
            set(row),
            {
                'id',
                'name',
                'slug',
                'owner',
                'active_members_count',
                'created_at',
                'last_access_at',
                'status',
                'is_deleted',
            },
        )
        self.assertEqual(row['owner']['email'], self.acme.owner.user.email)
        self.assertEqual(row['active_members_count'], 1)
        self.assertEqual(row['status'], 'active')

    def test_deleted_hidden_by_default(self):
        self.assertEqual(self.names(), {'Acme Inc', 'Globex Corp'})
        self.assertIn('Gone Ltd', self.names(deleted='true'))

    def test_filter_status(self):
        self.assertEqual(self.names(status='suspended'), {'Globex Corp'})

    def test_search_by_owner_email(self):
        self.assertEqual(self.names(search=self.acme.owner.user.email), {'Acme Inc'})

    def test_inverted_period_is_refused(self):
        response = self.client.get(
            self.list_url,
            data={'created_at_after': '2026-10-20', 'created_at_before': '2026-10-01'},
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_last_access_and_active_members_ignore_inactive_members(self):
        now = timezone.now()
        last_login = now - timedelta(days=1)
        MemberFactory(organization=self.acme, last_login_at=last_login)
        MemberFactory(organization=self.acme, last_login_at=now, is_active=False)
        response = self.client.get(self.list_url, data={'search': 'Acme'})
        row = response.data['results'][0]
        self.assertEqual(row['active_members_count'], 2)
        self.assertEqual(parse_datetime(row['last_access_at']), last_login)

    def test_order_by_name(self):
        response = self.client.get(self.list_url, data={'order_by': 'name'})
        names = [row['name'] for row in response.data['results']]
        self.assertEqual(names, sorted(names))


class PlatformOrganizationDetailTestCase(
    PlatformTestMixin, APITestCaseMixin, APITestCase
):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.url = reverse('platform:organizations-detail', args=[self.organization.id])
        self.authenticate_staff()

    def test_counts_storage_and_no_suspension(self):
        MemberFactory(organization=self.organization)
        TeamFactory(organization=self.organization)
        InvitationFactory(organization=self.organization)
        stored_file = StoredFileFactory(organization=self.organization)
        data = self.client.get(self.url).data
        self.assertEqual(data['counts']['active_members'], 2)
        self.assertEqual(data['counts']['teams'], 1)
        self.assertEqual(data['counts']['pending_invitations'], 1)
        stored_file.refresh_from_db()
        self.assertEqual(data['storage_bytes'], stored_file.size)
        self.assertIsNone(data['suspension'])
        self.assertIsNotNone(data['owner']['member_since'])

    def test_suspension_info(self):
        admin = UserFactory(platform_admin=True)
        organization = OrganizationFactory(suspended=True, suspended_by=admin)
        url = reverse('platform:organizations-detail', args=[organization.id])
        data = self.client.get(url).data
        self.assertEqual(data['suspension']['reason'], 'Chargeback under investigation')
        self.assertEqual(data['suspension']['suspended_by']['id'], admin.id)

    def test_not_found(self):
        url = reverse('platform:organizations-detail', args=[0])
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_members_tab_and_transfer_picker_filters(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        MemberFactory(organization=self.organization, is_active=False)
        url = reverse('platform:organizations-members', args=[self.organization.id])
        all_rows = self.client.get(url).data['results']
        self.assertEqual(len(all_rows), 3)
        picker = self.client.get(
            url, data={'is_active': 'true', 'exclude_owner': 'true'}
        ).data['results']
        self.assertEqual([row['id'] for row in picker], [member.id])

    def test_teams_and_pending_invitations_tabs(self):
        TeamFactory(organization=self.organization)
        InvitationFactory(organization=self.organization)
        InvitationFactory(organization=self.organization, is_accepted=True)
        teams_url = reverse('platform:organizations-teams', args=[self.organization.id])
        invitations_url = reverse(
            'platform:organizations-invitations', args=[self.organization.id]
        )
        self.assertEqual(self.client.get(teams_url).data['count'], 1)
        self.assertEqual(self.client.get(invitations_url).data['count'], 1)
