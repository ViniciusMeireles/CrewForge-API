import time

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.fields import PaginatedOptionsActiveOrganizationSerializer
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.generics.fields.options import (
    ListChoicesOptionsSerializer,
    OptionBaseSerializer,
    PaginatedOptionsSerializer,
)
from apps.generics.mixins.views import OptionsBaseModelMixin
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.teams import TeamFactory
from apps.teams.models.team import Team
from apps.teams.models.team_member import TeamMember
from apps.teams.views.team_members import TeamMemberViewSet

User = get_user_model()


class _TeamSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMember
        fields = ['team']
        options_extra_kwargs = {
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
        options_extra_kwargs = {'team': {'value_field_name': 'slug'}}


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


class PaginatedOptionsClassAttributesTestCase(SimpleTestCase):
    def test_default_filter_lookup_expr(self):
        field = PaginatedOptionsSerializer(queryset=Team.objects.all())
        self.assertEqual(field.filter_lookup_expr, 'exact')

    def test_organization_scoped_filter_lookup_expr(self):
        field = PaginatedOptionsActiveOrganizationSerializer(
            queryset=Team.objects.all()
        )
        self.assertEqual(field.filter_lookup_expr, 'icontains')

    def test_filter_lookup_expr_kwarg_overrides_class_attribute(self):
        field = PaginatedOptionsActiveOrganizationSerializer(
            queryset=Team.objects.all(),
            filter_lookup_expr='istartswith',
        )
        self.assertEqual(field.filter_lookup_expr, 'istartswith')

    def test_option_serializer_class_attribute_is_kept(self):
        class IntOption(OptionBaseSerializer):
            output_type = int

        class CustomOptions(PaginatedOptionsSerializer):
            option_serializer_class = IntOption

        field = CustomOptions(queryset=Team.objects.all())
        self.assertIs(field.get_option_serializer_class(), IntOption)


class ChoicesRegexFilterTestCase(SimpleTestCase):
    choices = [
        {'value': 'a', 'label': 'Administrator'},
        {'value': 'b', 'label': 'Viewer'},
        {'value': 'c', 'label': 'Gestão'},
    ]

    def _filter(self, pattern):
        request = Request(APIRequestFactory().get('/', {'role': pattern}))
        serializer = ListChoicesOptionsSerializer(
            child=serializers.DictField(), context={'request': request}
        )
        serializer.bind(field_name='role', parent=serializers.Serializer())
        serializer.parent._context = {'request': request}
        return [c['value'] for c in serializer.filter_choices(self.choices)]

    def test_matches_label(self):
        self.assertEqual(self._filter('^admin'), ['a'])

    def test_matches_value(self):
        self.assertEqual(self._filter('^b$'), ['b'])

    def test_ignores_accents_in_label(self):
        self.assertEqual(self._filter('gestao'), ['c'])

    def test_ignores_accents_in_pattern(self):
        self.assertEqual(self._filter('VIÉWER'), ['b'])
        self.assertEqual(self._filter('^gest[aã]o$'), ['c'])

    def test_catastrophic_pattern_is_bounded(self):
        self.choices = [
            {'value': 'logo', 'label': 'organization_logo_dark_theme_variant'},
            {'value': 'cover', 'label': 'organization_cover_light_theme_variant'},
        ]
        started = time.monotonic()
        with self.assertLogs('apps.generics.fields.options', level='WARNING'):
            result = self._filter(r'(\w|\w)*\d')
        self.assertEqual(result, [])
        self.assertLess(time.monotonic() - started, 1)


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

    def _role_values(self, pattern):
        response = self.client.get(self.create_url, {'role': pattern})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        return [option['value'] for option in response.data['role']]

    def test_choices_regex_filter(self):
        self.assertEqual(self._role_values('^ad'), ['admin'])
        self.assertEqual(self._role_values('MAN'), ['manager'])
        self.assertEqual(self._role_values('owner|member'), ['owner', 'member'])

    def test_choices_invalid_regex_is_literal(self):
        self.assertEqual(self._role_values('['), [])

    def test_choices_empty_value_returns_all(self):
        self.assertEqual(len(self._role_values('')), len(TeamMemberRoleChoices))

    def test_no_warning_logs_for_unconfigured_fields(self):
        with self.assertNoLogs('apps.generics.fields.options', level='WARNING'):
            self.client.get(self.create_url)
            self.client.get(self.create_url, {'member': ''})

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


class TeamMemberSearchTestCase(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.view = TeamMemberViewSet.as_view({'get': 'form_options_create'})

    def _get(self, params):
        request = APIRequestFactory().get('/', params)
        force_authenticate(request, user=self.organization.owner.user)
        request.session = {'organization_id': self.organization.pk}
        return self.view(request)

    def test_team_filters_by_name(self):
        TeamFactory(organization=self.organization, name='Alpha squad')
        TeamFactory(organization=self.organization, name='Beta squad')
        TeamFactory(organization=OrganizationFactory(), name='Alpha other org')
        response = self._get({'team': 'ALP'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            [r['label'] for r in response.data['team']['results']],
            ['Alpha squad'],
        )

    def test_member_filters_by_label_expression(self):
        member = MemberFactory(organization=self.organization, nickname='Zorro')
        MemberFactory(organization=OrganizationFactory(), nickname='Zorro')
        response = self._get({'member': 'zorr'})
        results = response.data['member']['results']
        self.assertEqual([r['value'] for r in results], [member.pk])
        self.assertIn('Zorro', results[0]['label'])

    def test_member_label_separates_nickname(self):
        member = MemberFactory(organization=self.organization, nickname='Zorro')
        response = self._get({'member': 'zorro'})
        label = response.data['member']['results'][0]['label']
        self.assertEqual(label, f'{member.user.full_name} (Zorro)')

    def test_team_search_ignores_accents(self):
        team = TeamFactory(organization=self.organization, name='Gestão de Pessoas')
        TeamFactory(organization=self.organization, name='Financeiro')
        for value in ('gestao', 'GESTÃO', 'pessôas'):
            with self.subTest(value=value):
                response = self._get({'team': value})
                self.assertEqual(
                    [r['value'] for r in response.data['team']['results']],
                    [team.pk],
                )

    def test_member_search_ignores_accents(self):
        member = MemberFactory(organization=self.organization, nickname='José')
        response = self._get({'member': 'jose'})
        self.assertEqual(
            [r['value'] for r in response.data['member']['results']], [member.pk]
        )


class UnconfiguredSearchTestCase(TestCase):
    def test_value_is_ignored_and_warning_logged(self):
        with self.assertLogs('apps.generics.fields.options', level='WARNING'):
            data = _render_options(_GroupPermissionsSerializer, {'permissions': 'x'})
        self.assertEqual(data['permissions']['count'], Permission.objects.count())

    def test_no_warning_without_value(self):
        with self.assertNoLogs('apps.generics.fields.options', level='WARNING'):
            _render_options(_GroupPermissionsSerializer, {'permissions': ''})
