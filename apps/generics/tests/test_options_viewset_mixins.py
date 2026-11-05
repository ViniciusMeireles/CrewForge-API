from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from django.urls import NoReverseMatch, URLResolver, get_resolver, reverse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.accounts.views.members import MemberViewSet
from apps.accounts.views.organization_images import OrganizationImageViewSet
from apps.accounts.views.signup import SignupViewSet
from apps.generics.fields.options import PaginatedOptionsBaseSerializer
from apps.generics.mixins.views import (
    FormOptionsMixin,
    OptionsBaseModelMixin,
)
from apps.generics.serializers.options import OptionsModelSerializer
from apps.teams.filters.team_member import TeamMemberFilter
from apps.teams.models.team_member import TeamMember
from apps.teams.serializers.team_member import (
    TeamMemberSerializer,
    TeamMemberUpdateSerializer,
)
from apps.teams.views.team_members import TeamMemberViewSet


def _options_fields(viewset_class, options_action):
    view = viewset_class()
    view.action = options_action
    return set(view.get_options_serializer_class()({}).get_fields())


class OptionsViewSetMixinsTestCase(SimpleTestCase):
    def test_form_options_mixin_declares_the_actions(self):
        class TV(FormOptionsMixin, viewsets.ModelViewSet):
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
        self.assertFalse(hasattr(TV, 'filter_options'))

    def test_base_mixin_declares_no_route(self):
        class TV(OptionsBaseModelMixin, viewsets.ModelViewSet):
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer

        self.assertEqual(TV.get_extra_actions(), [])

    def test_subclass_inherits_the_declared_routes(self):
        class Parent(FormOptionsMixin, viewsets.ModelViewSet):
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer

        class Child(Parent):
            pass

        self.assertEqual(
            {a.__name__ for a in Child.get_extra_actions()},
            {'form_options_create', 'form_options_update'},
        )

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


class OptionsCustomActionTestCase(SimpleTestCase):
    def test_write_action_uses_its_serializer(self):
        class TV(OptionsBaseModelMixin, viewsets.ModelViewSet):
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer
            options_custom_actions = {'change_role': 'form_options_change_role'}

            def get_serializer_class(self):
                if self.action == 'change_role':
                    return TeamMemberUpdateSerializer
                return TeamMemberSerializer

            @action(detail=True, methods=['patch'], url_path='change-role')
            def change_role(self, request, *args, **kwargs):
                pass

            @action(detail=False, methods=['get'], url_path='form-options-change-role')
            def form_options_change_role(self, request, *args, **kwargs):
                return self.form_options(request, *args, **kwargs)

        self.assertEqual(_options_fields(TV, 'form_options_change_role'), {'role'})

    def test_get_action_uses_its_filterset(self):
        class TV(OptionsBaseModelMixin, viewsets.ModelViewSet):
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer
            filter_backends = [DjangoFilterBackend]
            options_custom_actions = {'mine': 'filter_options_mine'}

            @action(
                detail=False,
                methods=['get'],
                url_path='mine',
                filterset_class=TeamMemberFilter,
                permission_classes=[IsAuthenticated],
            )
            def mine(self, request, *args, **kwargs):
                pass

            @action(detail=False, methods=['get'], url_path='mine/filter-options')
            def filter_options_mine(self, request, *args, **kwargs):
                return self.form_options(request, *args, **kwargs)

        self.assertIn('role__in', _options_fields(TV, 'filter_options_mine'))

    def test_unknown_custom_action_raises(self):
        class TV(OptionsBaseModelMixin, viewsets.ModelViewSet):
            queryset = TeamMember.objects.all()
            serializer_class = TeamMemberSerializer
            options_custom_actions = {'missing': 'form_options_missing'}

        view = TV()
        view.action = 'form_options_missing'
        with self.assertRaisesMessage(ImproperlyConfigured, 'missing'):
            view.get_options_serializer_class()

    def test_member_update_role_options(self):
        self.assertEqual(
            _options_fields(MemberViewSet, 'form_options_update_role'), {'role'}
        )
        reverse('accounts:members-form-options-update-role')
        reverse('accounts:invitations-filter-options-received')


def _iter_url_patterns(patterns):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from _iter_url_patterns(pattern.url_patterns)
        else:
            yield pattern


class OptionsRoutesBuildTestCase(SimpleTestCase):
    def test_every_options_route_builds_a_serializer_with_fields(self):
        checked = set()
        for pattern in _iter_url_patterns(get_resolver().url_patterns):
            viewset_class = getattr(pattern.callback, 'cls', None)
            action_name = (getattr(pattern.callback, 'actions', None) or {}).get('get')
            if not viewset_class or not issubclass(
                viewset_class, OptionsBaseModelMixin
            ):
                continue
            if action_name not in viewset_class.get_options_actions_inverse_map():
                continue
            checked.add((viewset_class.__name__, action_name))
            with self.subTest(viewset=viewset_class.__name__, action=action_name):
                self.assertTrue(_options_fields(viewset_class, action_name))
        self.assertIn(('TeamViewSet', 'filter_options'), checked)


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
            if not viewset_class.options_search:
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
