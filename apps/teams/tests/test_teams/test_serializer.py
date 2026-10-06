from django.test import RequestFactory
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.factories.teams import TeamFactory
from apps.teams.serializers.team import TeamSerializer


class TeamSerializerTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('teams:teams-list')

    def _detail_url(self, team):
        return reverse('teams:teams-detail', args=[team.id])

    def _team_payload(self, **overrides):
        team_data = TeamFactory.build()
        payload = {
            'name': team_data.name,
            'description': team_data.description,
        }
        payload.update(overrides)
        return payload

    def test_create_serializer_fields(self):
        payload = self._team_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        expected_fields = {
            'id',
            'name',
            'slug',
            'description',
            'organization',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
        }
        self.assertEqual(set(response.data.keys()), expected_fields)

    def test_detail_serializer_fields(self):
        team = TeamFactory(organization=self.organization)
        url = self._detail_url(team)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        expected_fields = {
            'id',
            'name',
            'slug',
            'description',
            'organization',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
        }
        self.assertEqual(set(response.data.keys()), expected_fields)

    def test_list_serializer_fields(self):
        TeamFactory(organization=self.organization)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        result = response.data['results'][0]
        expected_fields = {
            'id',
            'name',
            'slug',
            'description',
            'organization',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by',
            'member_count',
        }
        self.assertEqual(set(result.keys()), expected_fields)

    def test_validate_empty_name(self):
        payload = self._team_payload(name='')
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_auto_populates_organization(self):
        payload = self._team_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['organization'], self.organization.id)

    def test_validate_name_too_long(self):
        payload = self._team_payload(name='n' * 101)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_read_only_fields_ignored(self):
        payload = self._team_payload(
            id=99999,
            is_active=False,
        )
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertNotEqual(response.data['id'], 99999)
        self.assertTrue(response.data['is_active'])

    def test_read_only_organization_field(self):
        other_org = OrganizationFactory()
        payload = self._team_payload(organization=other_org.id)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['organization'], self.organization.id)

    def test_validate_duplicate_slug_active_returns_400(self):
        TeamFactory(organization=self.organization, name='Backend', slug='backend')
        payload = self._team_payload(name='Backend')
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_duplicate_after_soft_delete_returns_201(self):
        team = TeamFactory(
            organization=self.organization, name='Backend', slug='backend'
        )
        team.inactivate()
        payload = self._team_payload(name='Backend')
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_partial_update_without_name_keeps_slug(self):
        team = TeamFactory(
            organization=self.organization, name='Backend', slug='backend'
        )
        request = RequestFactory().get('/')
        request.user = self.organization.owner.user
        serializer = TeamSerializer(
            instance=team,
            data={'description': 'x'},
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        team.refresh_from_db()
        self.assertEqual(team.description, 'x')
        self.assertEqual(team.slug, 'backend')

    def test_update_with_name_regenerates_slug(self):
        team = TeamFactory(
            organization=self.organization, name='Backend', slug='backend'
        )
        url = self._detail_url(team)
        payload = self._team_payload(name='Platform')
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], 'platform')
