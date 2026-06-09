from django.test import TestCase

from apps.accounts.factories.organizations import (
    OrganizationFactory,
    OrganizationProfileFactory,
)
from apps.accounts.models.organization import OrganizationProfile


class OrganizationProfileModelTestCase(TestCase):
    def test_str(self):
        profile = OrganizationProfileFactory()
        self.assertEqual(str(profile), str(profile.organization))

    def test_filter_actives_all_active(self):
        OrganizationProfileFactory()
        self.assertEqual(OrganizationProfile.objects.filter_actives().count(), 1)

    def test_filter_actives_organization_inactive(self):
        OrganizationProfileFactory(organization__is_active=False)
        self.assertEqual(OrganizationProfile.objects.filter_actives().count(), 0)

    def test_filter_actives_self_inactive(self):
        OrganizationProfileFactory(is_active=False)
        self.assertEqual(OrganizationProfile.objects.filter_actives().count(), 0)

    def test_filter_inactives(self):
        OrganizationProfileFactory(
            organization=OrganizationFactory(is_active=False),
            is_active=False,
        )
        self.assertEqual(OrganizationProfile.objects.filter_inactives().count(), 1)

    def test_manager_get_or_none_found(self):
        profile = OrganizationProfileFactory()
        result = OrganizationProfile.objects.get_or_none(id=profile.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, profile.id)

    def test_manager_get_or_none_not_found(self):
        result = OrganizationProfile.objects.get_or_none(id=99999)
        self.assertIsNone(result)

    def test_cascade_organization_delete(self):
        profile = OrganizationProfileFactory()
        org = profile.organization
        org.delete()
        self.assertFalse(OrganizationProfile.objects.filter(id=profile.id).exists())

    def test_get_profile_creates_if_not_exists(self):
        org = OrganizationFactory()
        profile = org.get_profile()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.organization_id, org.id)
