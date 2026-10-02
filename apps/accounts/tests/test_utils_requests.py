from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.accounts.utils.requests import get_member, is_same_organization_scope


def _request(is_authenticated=True, is_active=True, session=None):
    user = SimpleNamespace(is_authenticated=is_authenticated, is_active=is_active)
    return SimpleNamespace(user=user, session=session or {})


class GetMemberTestCase(SimpleTestCase):
    def test_without_request(self):
        self.assertIsNone(get_member(None))

    def test_anonymous_user(self):
        self.assertIsNone(get_member(_request(is_authenticated=False)))

    def test_inactive_user(self):
        self.assertIsNone(get_member(_request(is_active=False)))

    def test_without_organization_session(self):
        self.assertIsNone(get_member(_request()))


class IsSameOrganizationScopeTestCase(SimpleTestCase):
    def test_without_organization_id(self):
        obj = SimpleNamespace(organization_id=1)
        self.assertFalse(is_same_organization_scope(obj, organization_id=None))

    def test_direct_lookup(self):
        obj = SimpleNamespace(organization_id=1)
        self.assertTrue(is_same_organization_scope(obj, organization_id=1))
        self.assertFalse(is_same_organization_scope(obj, organization_id=2))

    def test_nested_lookup(self):
        obj = SimpleNamespace(team=SimpleNamespace(organization_id=1))
        self.assertTrue(
            is_same_organization_scope(
                obj, organization_id=1, lookup='team.organization_id'
            )
        )

    def test_missing_attribute_in_path(self):
        obj = SimpleNamespace(team=None)
        self.assertFalse(
            is_same_organization_scope(
                obj, organization_id=1, lookup='team.organization_id'
            )
        )
