from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class SessionPlatformFieldsTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.session_url = reverse('accounts:session')

    def test_session_exposes_platform_role(self):
        self.client.force_authenticate(user=UserFactory(platform_role='support'))
        data = self.client.get(self.session_url).data
        self.assertEqual(data['user']['platform_role'], 'support')

    def test_session_organizations_carry_their_status(self):
        user = UserFactory()
        MemberFactory(user=user, organization=OrganizationFactory(suspended=True))
        self.client.force_authenticate(user=user)
        data = self.client.get(self.session_url).data
        self.assertEqual(data['organizations'][0]['status'], 'suspended')
