from django.contrib.auth.models import Group
from django.test import SimpleTestCase
from django.utils.functional import Promise
from drf_spectacular.generators import SchemaGenerator
from rest_framework import serializers

from apps.generics.mixins.views import OptionsBaseModelMixin
from apps.generics.utils.schema import get_form_options_parameters
from apps.teams.models.team_member import TeamMember
from apps.teams.serializers.team_member import (
    TeamMemberSerializer,
    TeamMemberUpdateSerializer,
)


class _TeamSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMember
        fields = ['team']
        options_extra_kwargs = {
            'team': {'label_field_name': 'name', 'filter_lookup_expr': 'icontains'},
        }


class _GroupPermissionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['permissions']


def _parameters(serializer_class, view_action='Create'):
    options_class = OptionsBaseModelMixin._get_options_serializer_class(
        serializer_class=serializer_class,
        view_action=view_action,
    )
    return {p.name: p for p in get_form_options_parameters(options_class)}


class FormOptionsParametersTestCase(SimpleTestCase):
    def test_field_and_pagination_parameters(self):
        parameters = _parameters(TeamMemberSerializer)
        self.assertEqual(
            list(parameters), ['role', 'team', 'member', 'page', 'page_size']
        )
        for parameter in parameters.values():
            self.assertEqual(parameter.location, 'query')
            self.assertFalse(parameter.required)

    def test_no_pagination_without_paginated_fields(self):
        parameters = _parameters(TeamMemberUpdateSerializer, 'Update')
        self.assertEqual(list(parameters), ['role'])

    def test_search_opt_in_is_described(self):
        description = _parameters(_TeamSearchSerializer)['team'].description
        self.assertIn('filters', description)
        self.assertIn('icontains', description)

    def test_configured_field_describes_search(self):
        description = _parameters(TeamMemberSerializer)['team'].description
        self.assertIn('filters', description)

    def test_unconfigured_field_value_is_ignored(self):
        parameters = _parameters(_GroupPermissionsSerializer)
        self.assertIn('ignored', parameters['permissions'].description)

    def test_descriptions_are_translatable(self):
        for parameter in _parameters(TeamMemberSerializer).values():
            with self.subTest(parameter=parameter.name):
                self.assertIsInstance(parameter.description, Promise)

    def test_component_description_is_translatable(self):
        options_class = OptionsBaseModelMixin._get_options_serializer_class(
            serializer_class=TeamMemberSerializer,
            view_action='Create',
        )
        description = options_class._spectacular_annotation['description']
        self.assertIsInstance(description, Promise)
        self.assertEqual(str(description), 'Form options to create a Team Member.')

    def test_page_size_mentions_maximum(self):
        description = _parameters(TeamMemberSerializer)['page_size'].description
        self.assertIn('100', description)


class FormOptionsSchemaTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = SchemaGenerator().get_schema(request=None, public=True)

    def _parameter_names(self, path):
        operation = self.schema['paths'][path]['get']
        return {p['name'] for p in operation.get('parameters', [])}

    def test_team_members_create_parameters(self):
        self.assertEqual(
            self._parameter_names('/api/teams/team-members/form-options-create/'),
            {'role', 'team', 'member', 'page', 'page_size'},
        )

    def test_team_members_update_parameters(self):
        self.assertEqual(
            self._parameter_names('/api/teams/team-members/form-options-update/'),
            {'role'},
        )

    def test_search_disabled_route_description(self):
        operation = self.schema['paths'][
            '/api/accounts/organization-images/form-options-create/'
        ]['get']
        description = {p['name']: p['description'] for p in operation['parameters']}
        self.assertIn('Search is disabled', str(description['image_type']))

    def test_invitations_create_parameters(self):
        self.assertEqual(
            self._parameter_names('/api/accounts/invitations/form-options-create/'),
            {'role'},
        )

    def test_response_fields_are_optional(self):
        component = self.schema['components']['schemas']['OptionsCreateTeamMember']
        self.assertNotIn('required', component)
