from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.models.organization import Organization
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.platform.tests.mixins import PlatformTestMixin


class PlatformOverviewTestCase(PlatformTestMixin, APITestCaseMixin, APITestCase):
    def test_counts(self):
        now = timezone.now()
        active = OrganizationFactory()
        MemberFactory(organization=active, last_login_at=now - timedelta(days=2))
        old = OrganizationFactory()
        Organization.objects.filter(pk=old.pk).update(
            created_at=now - timedelta(days=40)
        )
        OrganizationFactory(suspended=True)
        deleted = OrganizationFactory()
        deleted.is_active = False
        deleted.save(update_fields=['is_active'])
        UserFactory(blocked=True)
        self.authenticate_staff()

        data = self.client.get(reverse('platform:overview')).data

        self.assertEqual(data['organizations_total'], 3)
        self.assertEqual(data['organizations_suspended'], 1)
        self.assertEqual(data['organizations_new_7d'], 2)
        self.assertEqual(data['organizations_new_30d'], 2)
        self.assertEqual(data['organizations_active_30d'], 1)
        self.assertEqual(data['users_blocked'], 1)
        self.assertEqual(data['users_total'], data['users_new_30d'])
        self.assertGreaterEqual(data['users_total'], 6)
