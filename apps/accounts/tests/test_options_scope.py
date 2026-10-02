import copy
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from rest_framework import viewsets

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.fields import PaginatedOptionsActiveOrganizationSerializer
from apps.accounts.mixins.fields import PrimaryKeyRelatedField
from apps.accounts.mixins.views import ModelViewSetMixin
from apps.accounts.models.files import StoredFile
from apps.accounts.models.member import Member
from apps.accounts.serializers.files import StoredFileCreateUpdateModelSerializer
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.models.team_member import TeamMember

User = get_user_model()


class _GlobalOwnerSerializer(StoredFileCreateUpdateModelSerializer):
    class Meta(StoredFileCreateUpdateModelSerializer.Meta):
        options_extra_kwargs = {
            'owner': {'organization_scoped': False},
            'organization': {'organization_scoped': False},
        }


class OrganizationScopedOptionsTestCase(SimpleTestCase):
    def test_unscoped_relation_fails_at_class_creation(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'organization_scoped'):

            class UnscopedViewSet(ModelViewSetMixin, viewsets.ModelViewSet):
                queryset = StoredFile.objects.all()
                serializer_class = StoredFileCreateUpdateModelSerializer

    def test_explicit_global_relation_is_allowed(self):
        class GlobalViewSet(ModelViewSetMixin, viewsets.ModelViewSet):
            queryset = StoredFile.objects.all()
            serializer_class = _GlobalOwnerSerializer

        view = GlobalViewSet()
        view.action = 'form_options_create'
        fields = view.get_options_serializer_class()({}).get_fields()
        self.assertIn('owner', fields)
        self.assertIn('organization', fields)


class _LookupScopedSerializer(StoredFileCreateUpdateModelSerializer):
    class Meta(StoredFileCreateUpdateModelSerializer.Meta):
        options_extra_kwargs = {
            'owner': {
                'organization_lookup': 'members__organization_id',
                'label_field_name': 'email',
            },
            'organization': {
                'organization_lookup': 'id',
                'label_field_name': 'name',
            },
        }


class _InvalidLookupSerializer(StoredFileCreateUpdateModelSerializer):
    class Meta(StoredFileCreateUpdateModelSerializer.Meta):
        options_extra_kwargs = {
            'owner': {'organization_lookup': 'nope__organization_id'},
            'organization': {'organization_lookup': 'id'},
        }


class OrganizationLookupBuildTestCase(SimpleTestCase):
    def test_declared_lookup_is_allowed(self):
        class LookupViewSet(ModelViewSetMixin, viewsets.ModelViewSet):
            queryset = StoredFile.objects.all()
            serializer_class = _LookupScopedSerializer

        self.assertTrue(hasattr(LookupViewSet, 'form_options_create'))

    def test_invalid_lookup_fails_at_class_creation(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'nope__organization_id'):

            class InvalidViewSet(ModelViewSetMixin, viewsets.ModelViewSet):
                queryset = StoredFile.objects.all()
                serializer_class = _InvalidLookupSerializer


def _session_request(organization):
    user = SimpleNamespace(is_authenticated=True, is_active=True)
    return SimpleNamespace(user=user, session={'organization_id': organization.pk})


class OrganizationLookupScopeTestCase(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.other_organization = OrganizationFactory()
        self.context = {'request': _session_request(self.organization)}

    def test_options_field_scoped_by_lookup(self):
        field = PaginatedOptionsActiveOrganizationSerializer(
            queryset=User.objects.all(),
            organization_lookup='members__organization_id',
        )
        field._context = self.context
        users = set(field.get_queryset())
        self.assertIn(self.organization.owner.user, users)
        self.assertNotIn(self.other_organization.owner.user, users)

    def test_write_field_scoped_by_lookup(self):
        team_member = TeamMemberFactory(organization=self.organization)
        TeamMemberFactory(organization=self.other_organization)
        field = PrimaryKeyRelatedField(
            queryset=TeamMember.objects.all(),
            organization_lookup='team__organization_id',
        )
        field._context = self.context
        self.assertEqual(list(field.get_queryset()), [team_member])
        self.assertEqual(
            copy.deepcopy(field).organization_lookup, 'team__organization_id'
        )

    def test_only_relation_lookup_is_distinct(self):
        through_relation = PaginatedOptionsActiveOrganizationSerializer(
            queryset=User.objects.all(),
            organization_lookup='members__organization_id',
        )
        direct = PrimaryKeyRelatedField(queryset=Member.objects.all())
        for field, distinct in ((through_relation, True), (direct, False)):
            with self.subTest(field=field.__class__.__name__):
                field._context = self.context
                self.assertIs(field.get_queryset().query.distinct, distinct)

    def test_default_lookup_without_organization_id_is_unscoped(self):
        field = PrimaryKeyRelatedField(queryset=User.objects.all())
        field._context = self.context
        self.assertIsNone(field.get_organization_lookup(User))
