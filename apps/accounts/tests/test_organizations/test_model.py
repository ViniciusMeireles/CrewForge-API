from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory


class OrganizationModelTestCase(TestCase):
    def test_str(self):
        org = OrganizationFactory()
        self.assertEqual(str(org), org.name)

    def test_slug_unique(self):
        org = OrganizationFactory()
        with self.assertRaises(IntegrityError):
            OrganizationFactory(slug=org.slug)

    def test_members_includes_removed_members(self):
        org = OrganizationFactory()
        removed = MemberFactory(organization=org, is_active=False)
        self.assertIn(removed, org.members.all())
        self.assertEqual(org.members.count(), 2)
