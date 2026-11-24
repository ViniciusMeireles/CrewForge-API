from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.billing import entitlements
from apps.billing.models.plan import Plan


class EntitlementCatalogTestCase(SimpleTestCase):
    def test_catalog_keys(self):
        self.assertEqual(
            set(entitlements.CATALOG),
            {'max_members', 'max_teams', 'storage_mb', 'audit', 'audit_retention_days'},
        )

    def test_valid_values_pass(self):
        entitlements.validate_entitlements(
            {
                'max_members': 3,
                'max_teams': None,
                'storage_mb': 0,
                'audit': False,
                'audit_retention_days': 365,
            }
        )

    def test_unknown_key_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            entitlements.validate_entitlements({'max_projects': 3})
        self.assertIn('max_projects', ctx.exception.message_dict['entitlements'][0])

    def test_wrong_types_rejected(self):
        for values in (
            {'max_members': -1},
            {'max_members': '3'},
            {'max_members': True},
            {'audit': 1},
            {'audit': None},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                entitlements.validate_entitlements(values)

    def test_not_an_object_rejected(self):
        with self.assertRaises(ValidationError):
            entitlements.validate_entitlements([])

    def test_missing_key_reads_the_restrictive_default(self):
        plan = Plan(entitlements={})
        self.assertEqual(entitlements.value(plan, 'max_members'), 0)
        self.assertIs(entitlements.value(plan, 'audit'), False)
        self.assertIsNone(entitlements.value(plan, 'audit_retention_days'))

    def test_invalid_stored_value_reads_the_default(self):
        plan = Plan(entitlements={'max_teams': 'many', 'audit': 'yes'})
        self.assertEqual(entitlements.value(plan, 'max_teams'), 0)
        self.assertIs(entitlements.value(plan, 'audit'), False)

    def test_storage_bytes(self):
        self.assertEqual(
            entitlements.storage_bytes(Plan(entitlements={'storage_mb': 2})),
            2 * 1024 * 1024,
        )
        self.assertIsNone(
            entitlements.storage_bytes(Plan(entitlements={'storage_mb': None}))
        )
