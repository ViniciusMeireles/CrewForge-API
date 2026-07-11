from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.factories.organizations import OrganizationFactory


class OrganizationModelTestCase(TestCase):
    def test_str(self):
        org = OrganizationFactory()
        self.assertEqual(str(org), org.name)

    def test_slug_unique(self):
        org = OrganizationFactory()
        with self.assertRaises(IntegrityError):
            OrganizationFactory(slug=org.slug)
