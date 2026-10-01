from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, SimpleTestCase
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.generics.fields.options import PaginatedOptionsBaseSerializer
from apps.generics.mixins.views import OptionsBaseModelMixin
from apps.teams.models.team import Team
from apps.teams.models.team_member import TeamMember
from apps.teams.serializers.team_member import (
    TeamMemberSerializer,
    TeamMemberUpdateSerializer,
)


def _options_class(serializer_class, view_action='Create'):
    return OptionsBaseModelMixin._get_options_serializer_class(
        serializer_class=serializer_class,
        view_action=view_action,
    )


class _DeclaredRelatedSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.filter(name='restricted')
    )

    class Meta:
        model = TeamMember
        fields = ['team', 'member', 'role']


class _DeclaredReadOnlySerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(read_only=True)
    member = serializers.CharField(source='member.nickname')

    class Meta:
        model = TeamMember
        fields = ['team', 'member', 'role']


class _DeclaredChoiceSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=[('a', 'A'), ('b', 'B')])

    class Meta:
        model = TeamMember
        fields = ['role']


class _OptInSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMember
        fields = ['team', 'role']
        extra_kwargs = {
            'team': {
                'label_field_name': 'name',
                'filter_field_name': 'name',
                'filter_lookup_expr': 'icontains',
            },
            'role': {'write_only': True},
        }


class _UnsupportedKwargsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMember
        fields = ['role', 'team']
        extra_kwargs = {
            'role': {'allow_blank': True, 'max_length': 3},
            'team': {'html_cutoff': 10},
        }


class _DeclaredManyRelatedSerializer(serializers.ModelSerializer):
    permissions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.filter(codename__startswith='add_'),
    )

    class Meta:
        model = Group
        fields = ['permissions']


class OptionsSerializerFieldsTestCase(SimpleTestCase):
    def test_without_request_returns_all_fields(self):
        serializer = _options_class(TeamMemberSerializer)({}, context={})
        self.assertEqual(set(serializer.fields), {'role', 'team', 'member'})

    def test_with_django_request_does_not_raise(self):
        request = RequestFactory().get('/', {'role': ''})
        serializer = _options_class(TeamMemberSerializer)(
            {}, context={'request': request}
        )
        self.assertEqual(set(serializer.fields), {'role'})

    def test_with_drf_request_filters_by_query_param(self):
        request = Request(APIRequestFactory().get('/', {'role': ''}))
        serializer = _options_class(TeamMemberSerializer)(
            {}, context={'request': request}
        )
        self.assertEqual(set(serializer.fields), {'role'})

    def test_unknown_query_param_returns_all_fields(self):
        request = Request(APIRequestFactory().get('/', {'page': '1'}))
        serializer = _options_class(TeamMemberSerializer)(
            {}, context={'request': request}
        )
        self.assertEqual(set(serializer.fields), {'role', 'team', 'member'})


class OptionsModelSerializerFieldNamesTestCase(SimpleTestCase):
    def test_excludes_meta_read_only_fields(self):
        serializer = _options_class(TeamMemberUpdateSerializer, 'Update')({})
        self.assertEqual(set(serializer.get_fields()), {'role'})

    def test_excludes_non_option_fields(self):
        fields = set(_options_class(TeamMemberSerializer)({}).get_fields())
        self.assertNotIn('id', fields)
        self.assertNotIn('created_at', fields)

    def test_declared_related_field_reuses_queryset(self):
        serializer = _options_class(_DeclaredRelatedSerializer)({})
        declared = _DeclaredRelatedSerializer._declared_fields['team']
        self.assertIs(serializer.get_fields()['team'].queryset, declared.queryset)

    def test_declared_read_only_and_non_relational_fields_excluded(self):
        serializer = _options_class(_DeclaredReadOnlySerializer)({})
        self.assertEqual(set(serializer.get_fields()), {'role'})

    def test_declared_choice_field_uses_declared_choices(self):
        serializer = _options_class(_DeclaredChoiceSerializer)({})
        self.assertEqual(
            serializer.to_representation({})['role'],
            [{'value': 'a', 'label': 'A'}, {'value': 'b', 'label': 'B'}],
        )

    def test_declared_many_related_field_reuses_child_queryset(self):
        field = _options_class(_DeclaredManyRelatedSerializer)({}).get_fields()[
            'permissions'
        ]
        declared = _DeclaredManyRelatedSerializer._declared_fields['permissions']
        self.assertIsInstance(field, PaginatedOptionsBaseSerializer)
        self.assertIs(field.queryset, declared.child_relation.queryset)

    def test_unsupported_kwargs_are_dropped(self):
        fields = _options_class(_UnsupportedKwargsSerializer)({}).get_fields()
        self.assertEqual(set(fields), {'role', 'team'})

    def test_to_field_becomes_value_field_name(self):
        serializer = _options_class(TeamMemberSerializer)({})
        kwargs = serializer.include_extra_kwargs(
            {'to_field': 'slug', 'queryset': Team.objects.all(), 'many': True}, {}
        )
        self.assertEqual(kwargs['value_field_name'], 'slug')
        self.assertNotIn('to_field', kwargs)
        self.assertNotIn('many', kwargs)

    def test_opt_in_extra_kwargs_reach_options_field(self):
        team = _options_class(_OptInSerializer)({}).get_fields()['team']
        self.assertEqual(team.label_field_name, 'name')
        self.assertEqual(team.filter_field_name, 'name')
        self.assertEqual(team.filter_lookup_expr, 'icontains')

    def test_write_only_extra_kwarg_is_ignored(self):
        role = _options_class(_OptInSerializer)({}).get_fields()['role']
        self.assertFalse(role.write_only)
