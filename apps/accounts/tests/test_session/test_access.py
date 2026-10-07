from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.models.member import Member
from apps.accounts.serializers.session import MemberAccessSerializer
from apps.accounts.tests.mixins import APITestCaseMixin

EXPECTED_ACCESS = {
    MemberRoleChoices.OWNER: {
        'members': True,
        'invitations': True,
        'teams': True,
        'organization_settings': True,
    },
    MemberRoleChoices.ADMIN: {
        'members': True,
        'invitations': True,
        'teams': True,
        'organization_settings': False,
    },
    MemberRoleChoices.MANAGER: {
        'members': True,
        'invitations': False,
        'teams': True,
        'organization_settings': False,
    },
    MemberRoleChoices.MEMBER: {
        'members': True,
        'invitations': False,
        'teams': True,
        'organization_settings': False,
    },
}

AREA_LIST_URLS = {
    'members': 'accounts:members-list',
    'invitations': 'accounts:invitations-list',
    'teams': 'teams:teams-list',
}


class SessionAccessTestCase(APITestCaseMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.session_url = reverse('accounts:session')
        cls.organization = OrganizationFactory()

    def new_member(self, role: MemberRoleChoices, **kwargs) -> Member:
        return MemberFactory(organization=self.organization, role=role, **kwargs)

    def test_session_access_by_role(self):
        for role, expected in EXPECTED_ACCESS.items():
            with self.subTest(role=role):
                self.client.force_authenticate(member=self.new_member(role))
                response = self.client.get(self.session_url)
                self.assertEqual(response.status_code, http_status.HTTP_200_OK)
                self.assertEqual(response.data['member']['access'], expected)

    def test_organization_login_returns_access(self):
        for role, expected in EXPECTED_ACCESS.items():
            with self.subTest(role=role):
                member = self.new_member(role)
                self.client.force_authenticate(member=member, organization_auth=False)
                login_url = reverse(
                    'accounts:organizations-login', args=[self.organization.id]
                )
                response = self.client.post(login_url, format='json')
                self.assertEqual(response.status_code, http_status.HTTP_200_OK)
                self.assertEqual(response.data['member']['access'], expected)

    def test_superuser_has_all_access(self):
        user = UserFactory(is_superuser=True)
        member = self.new_member(MemberRoleChoices.MEMBER, user=user)
        self.client.force_authenticate(member=member)
        response = self.client.get(self.session_url)
        self.assertEqual(
            response.data['member']['access'],
            EXPECTED_ACCESS[MemberRoleChoices.OWNER],
        )

    def test_role_change_is_reflected_on_next_session_read(self):
        member = self.new_member(MemberRoleChoices.OWNER)
        self.client.force_authenticate(member=member)
        response = self.client.get(self.session_url)
        self.assertTrue(response.data['member']['access']['invitations'])

        Member.objects.filter(id=member.id).update(role=MemberRoleChoices.MEMBER)

        response = self.client.get(self.session_url)
        self.assertEqual(
            response.data['member']['access'],
            EXPECTED_ACCESS[MemberRoleChoices.MEMBER],
        )

    def test_access_follows_session_organization(self):
        member = self.new_member(MemberRoleChoices.OWNER)
        other_member = MemberFactory(user=member.user, role=MemberRoleChoices.MEMBER)
        self.client.force_authenticate(member=other_member)
        response = self.client.get(self.session_url)
        self.assertEqual(
            response.data['member']['access'],
            EXPECTED_ACCESS[MemberRoleChoices.MEMBER],
        )

    def test_access_matches_area_list_endpoints(self):
        for role in EXPECTED_ACCESS:
            self.client.force_authenticate(member=self.new_member(role))
            access = self.client.get(self.session_url).data['member']['access']
            for area, url_name in AREA_LIST_URLS.items():
                with self.subTest(role=role, area=area):
                    status = self.client.get(reverse(url_name)).status_code
                    self.assertEqual(
                        status == http_status.HTTP_200_OK,
                        access[area],
                    )
                    self.assertIn(
                        status,
                        {http_status.HTTP_200_OK, http_status.HTTP_403_FORBIDDEN},
                    )

    def test_access_serialization_adds_no_queries(self):
        member = Member.objects.select_related('user').get(
            id=self.new_member(MemberRoleChoices.ADMIN).id
        )
        with CaptureQueriesContext(connection) as queries:
            data = MemberAccessSerializer(member).data
        self.assertEqual(len(queries), 0)
        self.assertTrue(data['invitations'])
