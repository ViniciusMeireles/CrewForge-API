from django.test import SimpleTestCase
from django.urls import NoReverseMatch, URLResolver, get_resolver, reverse
from rest_framework import serializers, viewsets

from apps.accounts.views.members import MemberViewSet
from apps.accounts.views.organization_images import OrganizationImageViewSet
from apps.accounts.views.signup import SignupViewSet
from apps.generics.fields.options import PaginatedOptionsBaseSerializer
from apps.generics.mixins.views import OptionsModelMixin, OptionsModelViewSetMetaclass
from apps.generics.serializers.options import OptionsModelSerializer
from apps.teams.models.team import Team
from apps.teams.models.team_member import TeamMember
from apps.teams.serializers.team_member import TeamMemberSerializer
from apps.teams.views.team_members import TeamMemberViewSet


class _TeamNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['name']


def _options_fields(viewset_class, options_action):
    view = viewset_class()
    view.action = options_action
    return set(view.get_options_serializer_class()({}).get_fields())


class OptionsViewSetMetaclassTestCase(SimpleTestCase):
    def test_registers_actions_when_serializer_has_options(self):
        class TV(OptionsModelMixin, viewsets.ModelViewSet):
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer

        for action_name, url_path in (
            ('form_options_create', 'form-options-create'),
            ('form_options_update', 'form-options-update'),
        ):
            with self.subTest(action=action_name):
                view_func = getattr(TV, action_name)
                self.assertFalse(view_func.detail)
                self.assertEqual(view_func.url_path, url_path)
                self.assertEqual(dict(view_func.mapping), {'get': action_name})

    def test_skipped_when_serializer_has_no_options(self):
        class TV(OptionsModelMixin, viewsets.ModelViewSet):
            queryset = Team.objects.all()
            serializer_class = _TeamNameSerializer

        self.assertFalse(hasattr(TV, 'form_options_create'))
        self.assertFalse(hasattr(TV, 'form_options_update'))

    def test_skipped_when_no_get_method(self):
        class TV(OptionsModelMixin, viewsets.ModelViewSet):
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer
            http_method_names = ['post']

        self.assertFalse(hasattr(TV, 'form_options_create'))

    def test_raises_without_options_mixin(self):
        with self.assertRaises(TypeError):

            class TV(viewsets.ModelViewSet, metaclass=OptionsModelViewSetMetaclass):
                queryset = TeamMember.objects.all()
                serializer_class = TeamMemberSerializer

    def test_custom_url_path(self):
        class TV(OptionsModelMixin, viewsets.ModelViewSet):
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer
            url_path_options_create = 'custom-create'

        self.assertEqual(TV.form_options_create.url_path, 'custom-create')

    def test_options_actions_opt_out(self):
        class TV(OptionsModelMixin, viewsets.ModelViewSet):
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer
            options_actions = ()

        self.assertFalse(hasattr(TV, 'form_options_create'))
        self.assertFalse(hasattr(TV, 'form_options_update'))

    def test_options_actions_only_update(self):
        class TV(OptionsModelMixin, viewsets.ModelViewSet):
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer
            options_actions = ('update',)

        self.assertFalse(hasattr(TV, 'form_options_create'))
        self.assertTrue(hasattr(TV, 'form_options_update'))

    def test_subclass_opt_out_hides_inherited_routes(self):
        class Parent(OptionsModelMixin, viewsets.ModelViewSet):
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer

        class Child(Parent):
            options_actions = ('update',)

        def _action_names(viewset_class):
            return {a.__name__ for a in viewset_class.get_extra_actions()}

        self.assertEqual(
            _action_names(Parent), {'form_options_create', 'form_options_update'}
        )
        self.assertEqual(_action_names(Child), {'form_options_update'})

    def test_options_serializer_class_is_reusable(self):
        view = TeamMemberViewSet()
        view.action = 'form_options_create'
        first = view.get_options_serializer_class()
        second = view.get_options_serializer_class()
        self.assertIs(first, second)
        first({})
        second({})
        self.assertTrue(issubclass(first, OptionsModelSerializer))

    def test_signup_viewset_has_no_options(self):
        self.assertFalse(hasattr(SignupViewSet, 'form_options_create'))
        self.assertFalse(hasattr(SignupViewSet, 'form_options_update'))


class OptionsSourceSerializerTestCase(SimpleTestCase):
    def test_team_member_create_uses_create_serializer(self):
        self.assertEqual(
            _options_fields(TeamMemberViewSet, 'form_options_create'),
            {'role', 'team', 'member'},
        )

    def test_team_member_update_uses_update_serializer(self):
        self.assertEqual(
            _options_fields(TeamMemberViewSet, 'form_options_update'),
            {'role'},
        )

    def test_member_nested_user_not_exposed(self):
        for options_action in ('form_options_create', 'form_options_update'):
            with self.subTest(action=options_action):
                self.assertNotIn('user', _options_fields(MemberViewSet, options_action))

    def test_organization_image_nested_image_not_exposed(self):
        for options_action in ('form_options_create', 'form_options_update'):
            with self.subTest(action=options_action):
                self.assertEqual(
                    _options_fields(OrganizationImageViewSet, options_action),
                    {'image_type'},
                )


class OptionsRoutesTestCase(SimpleTestCase):
    present = (
        'accounts:invitations',
        'accounts:organization_images',
        'teams:team_members',
    )
    absent = (
        'accounts:members',
        'accounts:organizations',
        'accounts:organization_profiles',
        'accounts:stored_files',
        'teams:teams',
    )

    def test_routes_present(self):
        for basename in self.present:
            for suffix in ('create', 'update'):
                with self.subTest(basename=basename, suffix=suffix):
                    reverse(f'{basename}-form-options-{suffix}')

    def test_routes_absent(self):
        for basename in self.absent:
            for suffix in ('create', 'update'):
                with self.subTest(basename=basename, suffix=suffix):
                    with self.assertRaises(NoReverseMatch):
                        reverse(f'{basename}-form-options-{suffix}')


def _iter_url_patterns(patterns):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from _iter_url_patterns(pattern.url_patterns)
        else:
            yield pattern


class PaginatedOptionsSearchConfiguredTestCase(SimpleTestCase):
    def test_every_paginated_option_declares_search_field(self):
        checked = set()
        for pattern in _iter_url_patterns(get_resolver().url_patterns):
            viewset_class = getattr(pattern.callback, 'cls', None)
            action_name = (getattr(pattern.callback, 'actions', None) or {}).get('get')
            if not viewset_class or not hasattr(
                viewset_class, 'get_options_actions_inverse_map'
            ):
                continue
            if action_name not in viewset_class.get_options_actions_inverse_map():
                continue
            view = viewset_class()
            view.action = action_name
            fields = view.get_options_serializer_class()({}).get_fields()
            for field_name, field in fields.items():
                if not isinstance(field, PaginatedOptionsBaseSerializer):
                    continue
                checked.add((viewset_class.__name__, action_name, field_name))
                with self.subTest(
                    viewset=viewset_class.__name__, action=action_name, field=field_name
                ):
                    self.assertTrue(
                        field.filter_field_name or field.label_field_name,
                        'Paginated options must declare filter_field_name or '
                        'label_field_name in Meta.options_extra_kwargs',
                    )
        self.assertIn(('TeamMemberViewSet', 'form_options_create', 'member'), checked)
