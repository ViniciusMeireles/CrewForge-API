from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.platform.tests.mixins import PlatformTestMixin


class PlatformUserListTestCase(PlatformTestMixin, APITestCaseMixin, APITestCase):
    def setUp(self):
        self.list_url = reverse('platform:users-list')
        self.maria = UserFactory(first_name='Maria', last_name='Silva')
        self.bruno = UserFactory(
            first_name='Bruno', last_name='Dias', email_verified_at=None
        )
        self.diego = UserFactory(first_name='Diego', last_name='Rocha', blocked=True)
        self.gone = UserFactory(first_name='Gone', last_name='User', is_active=False)
        self.staff = self.authenticate_staff()

    def ids(self, **params):
        response = self.client.get(self.list_url, data=params)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        return {row['id'] for row in response.data['results']}

    def test_deleted_hidden_by_default(self):
        self.assertNotIn(self.gone.id, self.ids())
        self.assertIn(self.gone.id, self.ids(deleted='true'))

    def test_filters(self):
        self.assertEqual(self.ids(verified='false'), {self.bruno.id})
        self.assertEqual(self.ids(blocked='true'), {self.diego.id})
        self.assertEqual(self.ids(platform_role='support'), {self.staff.id})
        self.assertEqual(self.ids(search='Maria Silva'), {self.maria.id})

    def test_organizations_count_and_marks(self):
        MemberFactory(user=self.maria, organization=OrganizationFactory())
        response = self.client.get(self.list_url, data={'search': 'Maria'})
        row = response.data['results'][0]
        self.assertEqual(row['organizations_count'], 1)
        self.assertFalse(row['is_blocked'])
        self.assertEqual(row['platform_role'], 'none')


class PlatformUserDetailTestCase(PlatformTestMixin, APITestCaseMixin, APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.url = reverse('platform:users-detail', args=[self.user.id])

    def test_memberships_and_flags_for_support(self):
        organization = OrganizationFactory()
        MemberFactory(user=self.user, organization=organization)
        self.authenticate_staff('support')
        data = self.client.get(self.url).data
        self.assertEqual(data['memberships'][0]['organization']['id'], organization.id)
        self.assertIsNone(data['blocking'])
        self.assertTrue(data['can_impersonate'])
        self.assertFalse(data['can_block'])

    def test_admin_can_block_others_not_self(self):
        staff = self.authenticate_staff('admin')
        self.assertTrue(self.client.get(self.url).data['can_block'])
        own = self.client.get(reverse('platform:users-detail', args=[staff.id])).data
        self.assertFalse(own['can_block'])
        self.assertFalse(own['can_impersonate'])

    def test_blocked_user_cannot_be_impersonated_and_shows_blocking(self):
        blocked = UserFactory(blocked=True)
        self.authenticate_staff('support')
        data = self.client.get(reverse('platform:users-detail', args=[blocked.id])).data
        self.assertFalse(data['can_impersonate'])
        self.assertEqual(data['blocking']['reason'], 'Abuse report')

    def test_staff_cannot_be_impersonated(self):
        other_staff = UserFactory(platform_admin=True)
        self.authenticate_staff('support')
        url = reverse('platform:users-detail', args=[other_staff.id])
        self.assertFalse(self.client.get(url).data['can_impersonate'])
