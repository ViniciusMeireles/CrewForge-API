from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class MemberFilterTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:members-list')

        self.alice = MemberFactory(
            organization=self.organization,
            user__first_name='Alice',
            user__last_name='Smith',
            user__email='alice@example.com',
            nickname='alice_nick',
            role=MemberRoleChoices.ADMIN,
        )
        self.bob = MemberFactory(
            organization=self.organization,
            user__first_name='Bob',
            user__last_name='Jones',
            user__email='bob@example.com',
            nickname='bob_nick',
            role=MemberRoleChoices.MANAGER,
        )
        self.charlie = MemberFactory(
            organization=self.organization,
            user__first_name='Charlie',
            user__last_name='Brown',
            user__email='charlie@example.com',
            nickname='charlie_nick',
            role=MemberRoleChoices.MEMBER,
        )
        self.inactive_member = MemberFactory(
            organization=self.organization,
            user__first_name='Inactive',
            user__email='inactive@example.com',
            role=MemberRoleChoices.MEMBER,
            is_active=False,
        )

    def test_filter_email_icontains(self):
        response = self.client.get(self.list_url, {'email__icontains': 'alice'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(
            response.data['results'][0]['user']['email'], 'alice@example.com'
        )

    def test_filter_full_name_icontains(self):
        response = self.client.get(self.list_url, {'full_name__icontains': 'bob'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_nickname_exact(self):
        response = self.client.get(self.list_url, {'nickname': 'alice_nick'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_nickname_icontains(self):
        response = self.client.get(self.list_url, {'nickname__icontains': 'nick'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)

    def test_filter_role_exact(self):
        response = self.client.get(self.list_url, {'role': MemberRoleChoices.ADMIN})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_role_in(self):
        response = self.client.get(
            self.list_url,
            {'role__in': 'admin,manager'},
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_filter_is_active_false(self):
        response = self.client.get(self.list_url, {'is_active': False})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_filter_order_by_nickname_ascending(self):
        response = self.client.get(self.list_url, {'order_by': 'nickname'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        nicknames = [r['nickname'] for r in response.data['results']]
        self.assertEqual(nicknames, sorted(nicknames))

    def test_filter_order_by_nickname_descending(self):
        response = self.client.get(self.list_url, {'order_by': '-nickname'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        nicknames = [r['nickname'] for r in response.data['results']]
        self.assertEqual(nicknames, sorted(nicknames, reverse=True))

    def test_filter_order_by_created_at_ascending(self):
        response = self.client.get(self.list_url, {'order_by': 'created_at'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        created_at = [r['created_at'] for r in response.data['results']]
        self.assertEqual(created_at, sorted(created_at))

    def test_filter_order_by_created_at_descending(self):
        response = self.client.get(self.list_url, {'order_by': '-created_at'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        created_at = [r['created_at'] for r in response.data['results']]
        self.assertEqual(created_at, sorted(created_at, reverse=True))

    def test_filter_order_by_invalid_field(self):
        response = self.client.get(self.list_url, {'order_by': 'nonexistent_field'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_filter_order_by_with_other_filter(self):
        response = self.client.get(
            self.list_url,
            {'order_by': 'nickname', 'role': MemberRoleChoices.MEMBER},
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for r in response.data['results']:
            self.assertEqual(r['role'], MemberRoleChoices.MEMBER)
