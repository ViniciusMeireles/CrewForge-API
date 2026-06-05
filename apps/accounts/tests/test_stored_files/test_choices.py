from rest_framework.test import APITestCase

from apps.accounts.choices import StoredFileAccess
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory


class StoredFileAccessTestCase(APITestCase):
    def test_enum_has_6_values(self):
        values = [v.value for v in StoredFileAccess]
        self.assertEqual(len(values), 6)
        self.assertIn('owners_organization', values)
        self.assertIn('admins_organization', values)
        self.assertIn('managers_organization', values)
        self.assertIn('members_organization', values)
        self.assertIn('owner', values)
        self.assertIn('public', values)

    def test_organization_accesses_4_levels(self):
        org_accesses = StoredFileAccess.organization_accesses
        self.assertEqual(len(org_accesses), 4)
        self.assertIn(StoredFileAccess.MEMBERS_ORGANIZATION, org_accesses)
        self.assertIn(StoredFileAccess.MANAGERS_ORGANIZATION, org_accesses)
        self.assertIn(StoredFileAccess.ADMINS_ORGANIZATION, org_accesses)
        self.assertIn(StoredFileAccess.OWNERS_ORGANIZATION, org_accesses)

    def test_permissions_for_public(self):
        self.assertEqual(
            StoredFileAccess.permissions_for_public,
            [StoredFileAccess.PUBLIC],
        )

    def test_permissions_for_owner(self):
        self.assertEqual(
            StoredFileAccess.permissions_for_owner,
            [StoredFileAccess.OWNER, StoredFileAccess.PUBLIC],
        )

    def test_permissions_for_owner_organization(self):
        self.assertEqual(
            StoredFileAccess.permissions_for_owner_organization_updating,
            [
                StoredFileAccess.OWNERS_ORGANIZATION,
                StoredFileAccess.OWNER,
                StoredFileAccess.PUBLIC,
            ],
        )

    def test_permissions_for_admin_organization_updating(self):
        self.assertEqual(
            StoredFileAccess.permissions_for_admin_organization_updating,
            [
                StoredFileAccess.ADMINS_ORGANIZATION,
                StoredFileAccess.OWNERS_ORGANIZATION,
                StoredFileAccess.OWNER,
                StoredFileAccess.PUBLIC,
            ],
        )

    def test_permissions_for_manager_organization_updating(self):
        self.assertEqual(
            StoredFileAccess.permissions_for_manager_organization_updating,
            [
                StoredFileAccess.MANAGERS_ORGANIZATION,
                StoredFileAccess.ADMINS_ORGANIZATION,
                StoredFileAccess.OWNERS_ORGANIZATION,
                StoredFileAccess.OWNER,
                StoredFileAccess.PUBLIC,
            ],
        )

    def test_permissions_for_member_organization(self):
        self.assertEqual(
            StoredFileAccess.permissions_for_member_organization_updating,
            [
                StoredFileAccess.MEMBERS_ORGANIZATION,
                StoredFileAccess.MANAGERS_ORGANIZATION,
                StoredFileAccess.ADMINS_ORGANIZATION,
                StoredFileAccess.OWNERS_ORGANIZATION,
                StoredFileAccess.OWNER,
                StoredFileAccess.PUBLIC,
            ],
        )

    def test_permissions_levels_updating_all_keys(self):
        levels = StoredFileAccess.permissions_levels_updating
        self.assertEqual(len(levels), 6)
        for access in StoredFileAccess:
            self.assertIn(access, levels)

    def test_max_org_level_owner(self):
        org = OrganizationFactory()
        member = org.owner
        self.assertEqual(
            StoredFileAccess.max_org_level(member),
            StoredFileAccess.OWNERS_ORGANIZATION,
        )

    def test_max_org_level_admin(self):
        org = OrganizationFactory()
        admin = MemberFactory(organization=org, role='admin')
        self.assertEqual(
            StoredFileAccess.max_org_level(admin),
            StoredFileAccess.ADMINS_ORGANIZATION,
        )

    def test_max_org_level_manager(self):
        org = OrganizationFactory()
        manager = MemberFactory(organization=org, role='manager')
        self.assertEqual(
            StoredFileAccess.max_org_level(manager),
            StoredFileAccess.MANAGERS_ORGANIZATION,
        )

    def test_max_org_level_member(self):
        org = OrganizationFactory()
        member = MemberFactory(organization=org, role='member')
        self.assertEqual(
            StoredFileAccess.max_org_level(member),
            StoredFileAccess.MEMBERS_ORGANIZATION,
        )

    def test_max_org_level_none(self):
        self.assertIsNone(StoredFileAccess.max_org_level(None))
