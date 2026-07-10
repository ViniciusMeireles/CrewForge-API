from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.models.organization import Organization


class OrganizationModelTestCase(TestCase):
    def test_str(self):
        org = OrganizationFactory()
        self.assertEqual(str(org), org.name)

    def test_slug_unique(self):
        org = OrganizationFactory()
        with self.assertRaises(IntegrityError):
            OrganizationFactory(slug=org.slug)

    def test_filter_actives(self):
        OrganizationFactory()
        OrganizationFactory(is_active=False)
        result = Organization.objects.filter_actives()
        self.assertEqual(result.count(), 1)
        self.assertTrue(result.first().is_active)

    def test_get_or_none_found(self):
        org = OrganizationFactory()
        result = Organization.objects.get_or_none(id=org.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, org.id)

    def test_get_or_none_not_found(self):
        result = Organization.objects.get_or_none(id=99999)
        self.assertIsNone(result)

    def test_default_is_active(self):
        org = OrganizationFactory()
        self.assertTrue(org.is_active)

    def test_ordering(self):
        OrganizationFactory()
        OrganizationFactory()
        orgs = list(Organization.objects.all())
        self.assertEqual(orgs, sorted(orgs, key=lambda o: o.id, reverse=True))
