from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.generics.fields.options import (
    OptionBaseSerializer,
    PaginatedOptionsSerializer,
)
from apps.generics.mixins.views import OptionsBaseModelMixin
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.teams import TeamFactory
from apps.teams.models.team_member import TeamMember

User = get_user_model()


class _TeamSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMember
        fields = ['team']
        extra_kwargs = {
            'team': {
                'label_field_name': 'name',
                'filter_field_name': 'name',
                'filter_lookup_expr': 'icontains',
            },
        }


class _TeamSlugValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMember
        fields = ['team']
        extra_kwargs = {'team': {'value_field_name': 'slug'}}


class _GroupPermissionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['permissions']


def _render_options(serializer_class, params=None):
    request = Request(APIRequestFactory().get('/', params or {}))
    options_class = OptionsBaseModelMixin._get_options_serializer_class(
        serializer_class=serializer_class,
        view_action='Create',
    )
    return options_class({}, context={'request': request}).to_representation({})


class OptionBaseSerializerTestCase(SimpleTestCase):
    def test_non_type_output_type_returns_value(self):
        class JsonOption(OptionBaseSerializer):
            output_type = dict | list

        value = JsonOption().get_value_option({'_option_value': [1, 2]})
        self.assertEqual(value, [1, 2])

    def test_falsy_label_is_preserved(self):
        option = OptionBaseSerializer()
        self.assertEqual(option.get_label_option({'_option_label': 0}), '0')
        self.assertEqual(option.get_label_option({'_option_label': None}), '')

    def test_unordered_queryset_gets_pk_ordering(self):
        field = PaginatedOptionsSerializer(queryset=User.objects.all())
        self.assertTrue(field.get_queryset().ordered)


class PaginatedOptionsFilterTestCase(TestCase):
    def test_configured_filter_is_applied(self):
        organization = OrganizationFactory()
        TeamFactory(organization=organization, name='Alpha squad')
        TeamFactory(organization=organization, name='Beta squad')
        data = _render_options(_TeamSearchSerializer, {'team': 'alpha'})
        self.assertEqual(
            [result['label'] for result in data['team']['results']],
            ['Alpha squad'],
        )

    def test_value_field_name_without_label(self):
        organization = OrganizationFactory()
        team = TeamFactory(organization=organization)
        data = _render_options(_TeamSlugValueSerializer)
        result = next(r for r in data['team']['results'] if r['value'] == team.slug)
        self.assertEqual(result['label'], str(team))


class ToManyRelationOptionsTestCase(TestCase):
    def test_many_to_many_renders_single_envelope(self):
        data = _render_options(_GroupPermissionsSerializer)
        self.assertEqual(
            set(data['permissions']),
            {'count', 'num_pages', 'page_number', 'results'},
        )
        self.assertEqual(data['permissions']['count'], Permission.objects.count())


class TeamMemberFormOptionsTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.create_url = reverse('teams:team_members-form-options-create')
        self.update_url = reverse('teams:team_members-form-options-update')

    def test_shapes(self):
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            response.data['role'],
            [
                {'value': value, 'label': str(label)}
                for value, label in TeamMemberRoleChoices.choices
            ],
        )
        for field_name in ('team', 'member'):
            with self.subTest(field=field_name):
                self.assertEqual(
                    set(response.data[field_name]),
                    {'count', 'num_pages', 'page_number', 'results'},
                )

    def test_update_only_exposes_role(self):
        response = self.client.get(self.update_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(set(response.data), {'role'})

    def test_field_selection(self):
        response = self.client.get(self.create_url, {'team': ''})
        self.assertEqual(set(response.data), {'team'})

    def test_pagination(self):
        TeamFactory.create_batch(size=7, organization=self.organization)
        response = self.client.get(
            self.create_url, {'team': '', 'page_size': 5, 'page': 2}
        )
        team = response.data['team']
        self.assertEqual(team['count'], 7)
        self.assertEqual(team['num_pages'], 2)
        self.assertEqual(team['page_number'], 2)
        self.assertEqual(len(team['results']), 2)

    def test_invalid_page_returns_404(self):
        response = self.client.get(self.create_url, {'team': '', 'page': 99})
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_no_warning_logs_for_unconfigured_fields(self):
        with self.assertNoLogs('apps.generics.fields.options', level='WARNING'):
            self.client.get(self.create_url)

    def test_scoped_to_session_organization_and_active(self):
        own_team = TeamFactory(organization=self.organization)
        TeamFactory(organization=self.organization, is_active=False)
        TeamFactory(organization=OrganizationFactory())
        own_member = MemberFactory(organization=self.organization)
        MemberFactory(organization=self.organization, is_active=False)
        other_member = MemberFactory(organization=OrganizationFactory())

        response = self.client.get(self.create_url)

        team_values = {r['value'] for r in response.data['team']['results']}
        self.assertEqual(team_values, {own_team.pk})
        member_values = {r['value'] for r in response.data['member']['results']}
        self.assertIn(own_member.pk, member_values)
        self.assertIn(self.organization.owner.pk, member_values)
        self.assertNotIn(other_member.pk, member_values)
        self.assertEqual(response.data['member']['count'], 2)
