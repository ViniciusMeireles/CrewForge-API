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
