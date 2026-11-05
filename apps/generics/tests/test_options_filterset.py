from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from django.utils.functional import Promise
from django_filters.rest_framework import filters, filterset
from drf_spectacular.generators import SchemaGenerator
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.accounts.mixins.views import ModelViewSetMixin
from apps.accounts.models.files import StoredFile
from apps.accounts.serializers.files import StoredFileCreateUpdateModelSerializer
from apps.generics.fields.options import PaginatedOptionsBaseSerializer
from apps.generics.mixins.views import FilterOptionsMixin, OptionsBaseModelMixin
from apps.generics.serializers.options import OptionsFilterSetSerializer
from apps.generics.utils.schema import get_form_options_parameters
from apps.teams.models.team import Team
from apps.teams.models.team_member import TeamMember
from apps.teams.serializers.team_member import TeamMemberSerializer
from apps.teams.views.teams import TeamViewSet


def _priority_choices():
    return [('high', 'High'), ('low', 'Low')]


class _TeamMemberFilter(filterset.FilterSet):
    team_slug = filters.ModelChoiceFilter(
        field_name='team',
        queryset=Team.objects.all(),
        to_field_name='slug',
        label='Team slug',
        help_text='Filter by the team slug',
    )
    priority = filters.ChoiceFilter(choices=_priority_choices, method='noop')
    team_name = filters.CharFilter(field_name='team__name', lookup_expr='icontains')
    flagged = filters.BooleanFilter(method='noop')
    role_method = filters.CharFilter(field_name='role', method='noop')
    order_by = filters.OrderingFilter(fields=['role'])

    class Meta:
        model = TeamMember
        fields = {
            'team': ['exact'],
            'role': ['exact', 'in', 'icontains'],
            'is_active': ['exact'],
        }
        options_extra_kwargs = {
            'team': {'label_field_name': 'name'},
        }

    def noop(self, queryset, name, value):
        return queryset


class _TextOnlyFilter(filterset.FilterSet):
    class Meta:
        model = Team
        fields = {'name': ['exact', 'icontains']}


def _filter_options_class(filterset_class=_TeamMemberFilter):
    return OptionsBaseModelMixin._get_filter_options_serializer_class(filterset_class)


def _fields(filterset_class=_TeamMemberFilter, context=None):
    return _filter_options_class(filterset_class)({}, context=context or {}).fields


class OptionsFilterSetSerializerTestCase(SimpleTestCase):
    def test_only_choice_and_relation_filters(self):
        self.assertEqual(
            set(_fields()),
            {'team', 'team_slug', 'priority', 'role', 'role__in', 'order_by'},
        )

    def test_field_types(self):
        fields = _fields()
        for name in ('team', 'team_slug'):
            with self.subTest(field=name):
                self.assertIsInstance(fields[name], PaginatedOptionsBaseSerializer)
        for name in ('priority', 'role', 'role__in', 'order_by'):
            with self.subTest(field=name):
                self.assertNotIsInstance(fields[name], PaginatedOptionsBaseSerializer)

    def test_in_lookup_uses_model_field_choices(self):
        fields = _fields()
        self.assertEqual(fields['role__in'].initial_data, fields['role'].initial_data)

    def test_callable_choices(self):
        values = [o['value'] for o in _fields()['priority'].initial_data]
        self.assertEqual(values, ['high', 'low'])

    def test_ordering_choices(self):
        values = [o['value'] for o in _fields()['order_by'].initial_data]
        self.assertEqual(values, ['role', '-role'])

    def test_to_field_name_becomes_value_field(self):
        self.assertEqual(_fields()['team_slug'].value_field_name, 'slug')

    def test_options_extra_kwargs_are_merged(self):
        field = _fields()['team']
        self.assertEqual(field.label_field_name, 'name')
        self.assertFalse(field.required)

    def test_method_filter_does_not_inherit_model_choices(self):
        self.assertNotIn('role_method', _fields())

    def test_filter_label_and_help_text_are_kept(self):
        field = _fields()['team_slug']
        self.assertEqual(field.label, 'Team slug')
        self.assertEqual(field.help_text, 'Filter by the team slug')

    def test_unknown_filter_in_options_extra_kwargs_fails(self):
        class TypoFilter(_TextOnlyFilter):
            class Meta(_TextOnlyFilter.Meta):
                options_extra_kwargs = {'nme': {'label_field_name': 'name'}}

        with self.assertRaisesMessage(ImproperlyConfigured, "['nme']"):
            _fields(TypoFilter)

    def test_unknown_kwarg_in_options_extra_kwargs_fails(self):
        class TypoFilter(_TeamMemberFilter):
            class Meta(_TeamMemberFilter.Meta):
                options_extra_kwargs = {'team': {'label_field': 'name'}}

        with self.assertRaisesMessage(ImproperlyConfigured, "['label_field']"):
            _fields(TypoFilter)

    def test_field_selection_by_query_param(self):
        request = Request(APIRequestFactory().get('/', {'role': ''}))
        self.assertEqual(set(_fields(context={'request': request})), {'role'})

    def test_class_is_cached(self):
        self.assertIs(_filter_options_class(), _filter_options_class())
        self.assertTrue(issubclass(_filter_options_class(), OptionsFilterSetSerializer))

    def test_component_description(self):
        description = _filter_options_class()._spectacular_annotation['description']
        self.assertIsInstance(description, Promise)
        self.assertEqual(str(description), 'Filter options for listing Team Members.')

    def test_parameters(self):
        options_class = _filter_options_class()
        parameters = [p.name for p in get_form_options_parameters(options_class)]
        self.assertEqual(
            parameters,
            [
                'team',
                'role',
                'role__in',
                'team_slug',
                'priority',
                'order_by',
                'page',
                'page_size',
            ],
        )


class FilterOptionsRouteTestCase(SimpleTestCase):
    def test_mixin_declares_the_action(self):
        class TV(FilterOptionsMixin, viewsets.ModelViewSet):
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer
            filterset_class = _TeamMemberFilter

        self.assertFalse(TV.filter_options.detail)
        self.assertEqual(TV.filter_options.url_path, 'filter-options')
        self.assertEqual(dict(TV.filter_options.mapping), {'get': 'filter_options'})
        self.assertEqual(
            {a.__name__ for a in TV.get_extra_actions()}, {'filter_options'}
        )

    def test_without_django_filter_backend_is_not_found(self):
        class TV(FilterOptionsMixin, viewsets.ModelViewSet):
            permission_classes = [AllowAny]
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer
            filterset_class = _TeamMemberFilter
            filter_backends = []

        response = TV.as_view({'get': 'filter_options'})(APIRequestFactory().get('/'))
        self.assertEqual(response.status_code, 404)

    def test_without_filterset_is_not_found(self):
        class TV(FilterOptionsMixin, viewsets.ModelViewSet):
            permission_classes = [AllowAny]
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer

        response = TV.as_view({'get': 'filter_options'})(APIRequestFactory().get('/'))
        self.assertEqual(response.status_code, 404)

    def test_filter_options_include_the_order_by_of_the_filterset(self):
        view = TeamViewSet()
        view.action = 'filter_options'
        fields = view.get_options_serializer_class()({}).get_fields()
        self.assertIn('order_by', fields)


class _StoredFileFilter(filterset.FilterSet):
    class Meta:
        model = StoredFile
        fields = {'owner': ['exact']}


class _StoredFileLookupFilter(_StoredFileFilter):
    class Meta(_StoredFileFilter.Meta):
        options_extra_kwargs = {
            'owner': {'organization_lookup': 'members__organization_id'},
        }


class _StoredFileTypoFilter(_StoredFileFilter):
    class Meta(_StoredFileFilter.Meta):
        options_extra_kwargs = {
            'owner': {
                'organization_lookup': 'members__organization_id',
                'organization_filter': {'members__is_active': True},
            },
        }


def _filter_option_fields(filterset):
    class ScopedViewSet(FilterOptionsMixin, ModelViewSetMixin, viewsets.ModelViewSet):
        queryset = StoredFile.objects.all()
        serializer_class = StoredFileCreateUpdateModelSerializer
        filterset_class = filterset

    view = ScopedViewSet()
    view.action = 'filter_options'
    return view.get_options_serializer_class()({}).get_fields()


class FilterOptionsOrganizationScopeTestCase(SimpleTestCase):
    def test_misspelled_organization_kwarg_fails(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'organization_filter'):
            _filter_option_fields(_StoredFileTypoFilter)

    def test_unscoped_relation_fails(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'OptionsListStoredFile'):
            _filter_option_fields(_StoredFileFilter)

    def test_declared_lookup_is_allowed(self):
        field = _filter_option_fields(_StoredFileLookupFilter)['owner']
        self.assertEqual(field.organization_lookup, 'members__organization_id')


class FilterOptionsSchemaTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = SchemaGenerator().get_schema(request=None, public=True)

    def test_team_members_parameters(self):
        operation = self.schema['paths']['/api/teams/team-members/filter-options/'][
            'get'
        ]
        self.assertEqual(
            {p['name'] for p in operation['parameters']},
            {'team', 'member', 'role', 'role__in', 'order_by', 'page', 'page_size'},
        )
        self.assertEqual(str(operation['summary']), 'Filter options')
        self.assertIn('team members list', str(operation['description']))

    def test_invitations_parameters(self):
        operation = self.schema['paths']['/api/accounts/invitations/filter-options/'][
            'get'
        ]
        self.assertEqual(
            {p['name'] for p in operation['parameters']},
            {'status', 'role', 'role__in', 'order_by'},
        )
