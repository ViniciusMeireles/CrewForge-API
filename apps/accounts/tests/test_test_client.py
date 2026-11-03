import secrets
from unittest import mock

from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class ForceAuthenticateMemberTestCase(APITestCaseMixin, APITestCase):
    def test_builds_the_session_without_a_request(self):
        member = MemberFactory()
        with mock.patch.object(self.client, 'post') as post:
            self.client.force_authenticate(member=member)
        post.assert_not_called()
        response = self.client.get(reverse('accounts:session'))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['organization']['id'], member.organization_id)
        self.assertEqual(response.data['member']['id'], member.id)

    def test_inactive_member_keeps_a_session_the_api_denies(self):
        member = MemberFactory(is_active=False)
        self.client.force_authenticate(member=member)
        self.assertEqual(self.client.session['organization_id'], member.organization_id)
        response = self.client.get(reverse('accounts:members-list'))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_without_organization_auth_has_no_session(self):
        member = MemberFactory()
        self.client.force_authenticate(member=member, organization_auth=False)
        self.assertIsNone(self.client.session.get('organization_id'))


class UserFactoryPasswordTestCase(APITestCase):
    def test_given_password_is_stored(self):
        given = secrets.token_urlsafe(16)
        user = UserFactory(password=given)
        self.assertTrue(user.check_password(given))

    def test_default_password_without_argument(self):
        from apps.accounts.factories.users import DEFAULT_PASSWORD

        self.assertTrue(UserFactory().check_password(DEFAULT_PASSWORD))
