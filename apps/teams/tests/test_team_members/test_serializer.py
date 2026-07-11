from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory


class TeamMemberSerializerTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('teams:team_members-list')

    def _detail_url(self, tm):
        return reverse('teams:team_members-detail', args=[tm.id])

    def _tm_payload(self, **overrides):
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {
            'team': team.id,
            'member': member.id,
            'role': TeamMemberRoleChoices.MEMBER,
        }
        payload.update(overrides)
        return payload

    def test_create_serializer_fields(self):
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {
            'team': team.id,
            'member': member.id,
            'role': TeamMemberRoleChoices.MEMBER,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        expected_fields = {
            'id',
            'team',
            'member',
            'role',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
        }
        self.assertEqual(set(response.data.keys()), expected_fields)

    def test_detail_serializer_fields(self):
        tm = TeamMemberFactory(organization=self.organization)
        url = self._detail_url(tm)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        expected_fields = {
            'id',
            'team',
            'member',
            'role',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
        }
        self.assertEqual(set(response.data.keys()), expected_fields)

    def test_list_serializer_fields(self):
        TeamMemberFactory(organization=self.organization)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        result = response.data['results'][0]
        expected_fields = {
            'id',
            'team',
            'member',
            'role',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
        }
        self.assertEqual(set(result.keys()), expected_fields)

    def test_validate_duplicate_team_member(self):
        tm = TeamMemberFactory(organization=self.organization)
        payload = {
            'team': tm.team.id,
            'member': tm.member.id,
            'role': TeamMemberRoleChoices.MEMBER,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_validate_invalid_role(self):
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {'team': team.id, 'member': member.id, 'role': 'invalid_role'}
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_auto_populates_from_context(self):
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {'team': team.id, 'member': member.id}
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data['created_by'])
        self.assertIsNotNone(response.data['updated_by'])

    def test_validate_member_from_different_org(self):
        other_org = OrganizationFactory()
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=other_org)
        payload = self._tm_payload(team=team.id, member=member.id)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_validate_team_from_different_org(self):
        other_org = OrganizationFactory()
        team = TeamFactory(organization=other_org)
        member = MemberFactory(organization=self.organization)
        payload = self._tm_payload(team=team.id, member=member.id)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_read_only_fields_ignored(self):
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = {
            'team': team.id,
            'member': member.id,
            'role': TeamMemberRoleChoices.MEMBER,
            'id': 99999,
            'is_active': False,
        }
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_active'])
        self.assertNotEqual(response.data['id'], 99999)

    def test_auto_populates_organization_from_context(self):
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        payload = self._tm_payload(team=team.id, member=member.id)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_by'], self.organization.owner.user.id)
        self.assertEqual(response.data['updated_by'], self.organization.owner.user.id)
