from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from rest_framework import viewsets

from apps.accounts.mixins.views import ModelViewSetMixin
from apps.accounts.models.files import StoredFile
from apps.accounts.serializers.files import StoredFileCreateUpdateModelSerializer


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
