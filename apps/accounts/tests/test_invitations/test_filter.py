from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class InvitationFilterTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:invitations-list')

    def _create_invitation(self, **kwargs):
        return InvitationFactory(organization=self.organization, **kwargs)

    def test_filter_email_exact(self):
        self._create_invitation(email='target@example.com')
        self._create_invitation()
        response = self.client.get(self.list_url, {'email': 'target@example.com'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_email_icontains(self):
        self._create_invitation(email='match_this@example.com')
        self._create_invitation()
        response = self.client.get(self.list_url, {'email__icontains': 'match'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_is_accepted_true(self):
        self._create_invitation(is_accepted=True)
        self._create_invitation(is_accepted=False)
        response = self.client.get(self.list_url, {'is_accepted': True})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertTrue(result['is_accepted'])

    def test_filter_is_accepted_false(self):
        self._create_invitation(is_accepted=True)
        self._create_invitation(is_accepted=False)
        response = self.client.get(self.list_url, {'is_accepted': False})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertFalse(result['is_accepted'])

    def test_filter_is_expired_true(self):
        self._create_invitation(is_expired=True)
        self._create_invitation(is_expired=False)
        response = self.client.get(self.list_url, {'is_expired': True})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertTrue(result['is_expired'])

    def test_filter_expired_at_gt(self):
        future = timezone.now() + timedelta(days=30)
        past = timezone.now() - timedelta(days=1)
        self._create_invitation(expired_at=future)
        self._create_invitation(expired_at=past)
        response = self.client.get(self.list_url, {'expired_at__gt': timezone.now()})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertGreater(result['expired_at'], timezone.now().isoformat())

    def test_filter_expired_at_lt(self):
        future = timezone.now() + timedelta(days=30)
        past = timezone.now() - timedelta(days=1)
        self._create_invitation(expired_at=future)
        self._create_invitation(expired_at=past)
        response = self.client.get(self.list_url, {'expired_at__lt': timezone.now()})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertLess(result['expired_at'], timezone.now().isoformat())

    def test_filter_role_exact(self):
        self._create_invitation(role=MemberRoleChoices.ADMIN)
        self._create_invitation(role=MemberRoleChoices.MEMBER)
        response = self.client.get(self.list_url, {'role': MemberRoleChoices.ADMIN})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertEqual(result['role'], MemberRoleChoices.ADMIN)

    def test_filter_role_in(self):
        self._create_invitation(role=MemberRoleChoices.ADMIN)
        self._create_invitation(role=MemberRoleChoices.MANAGER)
        self._create_invitation(role=MemberRoleChoices.MEMBER)
        response = self.client.get(
            self.list_url,
            {'role__in': f'{MemberRoleChoices.ADMIN},{MemberRoleChoices.MANAGER}'},
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertIn(
                result['role'],
                [MemberRoleChoices.ADMIN, MemberRoleChoices.MANAGER],
            )

    def test_filter_combined(self):
        target_email = 'filter_combined@example.com'
        future = timezone.now() + timedelta(days=30)
        self._create_invitation(
            email=target_email,
            role=MemberRoleChoices.ADMIN,
            expired_at=future,
            is_expired=False,
        )
        self._create_invitation()
        response = self.client.get(
            self.list_url,
            {
                'email': target_email,
                'role': MemberRoleChoices.ADMIN,
                'is_expired': False,
            },
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
