from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.models.organization import Organization
from apps.billing.backfill import (
    create_courtesy_subscriptions,
    remove_seed_plans,
    seed_plans,
)
from apps.billing.choices import SubscriptionCourtesyChoices, SubscriptionStatusChoices
from apps.billing.factories.plans import PlanFactory
from apps.billing.models.plan import Plan
from apps.billing.models.subscription import Subscription


class SeedPlansTestCase(TestCase):
    def test_seed_values(self):
        free = Plan.objects.get(code='free')
        pro = Plan.objects.get(code='pro')
        self.assertTrue(free.is_free)
        self.assertFalse(free.is_default)
        self.assertEqual(free.monthly_price, Decimal('0.00'))
        self.assertEqual(
            free.entitlements,
            {
                'max_members': 3,
                'max_teams': 1,
                'storage_mb': 100,
                'audit': False,
                'audit_retention_days': None,
            },
        )
        self.assertTrue(pro.is_default)
        self.assertEqual(pro.trial_days, 14)
        self.assertEqual(pro.monthly_price, Decimal('99.00'))
        self.assertEqual(pro.annual_price, Decimal('990.00'))
        self.assertEqual(
            pro.entitlements,
            {
                'max_members': 25,
                'max_teams': 10,
                'storage_mb': 5120,
                'audit': True,
                'audit_retention_days': 365,
            },
        )

    def test_seed_skips_a_product_catalog(self):
        Plan.objects.filter(code='pro').update(name='Pro (product)')
        self.assertEqual(seed_plans(Plan), 0)
        self.assertEqual(Plan.objects.get(code='pro').name, 'Pro (product)')

    def test_seed_fills_an_empty_catalog(self):
        Subscription.objects.all().delete()
        Plan.objects.all().delete()
        self.assertEqual(seed_plans(Plan), 2)
        self.assertEqual(
            set(Plan.objects.values_list('code', flat=True)), {'free', 'pro'}
        )

    def test_remove_keeps_plans_in_use(self):
        OrganizationFactory(subscription__plan=Plan.objects.get(code='pro'))
        remove_seed_plans(Plan)
        self.assertFalse(Plan.objects.filter(code='free').exists())
        self.assertTrue(Plan.objects.filter(code='pro').exists())


class CourtesyBackfillTestCase(TestCase):
    def test_backfill_creates_legacy_pro(self):
        organizations = [
            OrganizationFactory(subscription=False),
            OrganizationFactory(subscription=False, is_active=False),
        ]
        kept = OrganizationFactory()
        created = create_courtesy_subscriptions(Organization, Subscription, Plan)
        self.assertEqual(created, 2)
        for organization in organizations:
            subscription = Subscription.objects.get(organization=organization)
            self.assertEqual(subscription.plan.code, 'pro')
            self.assertEqual(subscription.status, SubscriptionStatusChoices.ACTIVE)
            self.assertIsNone(subscription.cycle)
            self.assertEqual(subscription.courtesy, SubscriptionCourtesyChoices.LEGACY)
            self.assertTrue(subscription.is_complimentary)
        self.assertEqual(Subscription.objects.get(organization=kept).courtesy, '')

    def test_backfill_is_idempotent(self):
        OrganizationFactory(subscription=False)
        create_courtesy_subscriptions(Organization, Subscription, Plan)
        self.assertEqual(
            create_courtesy_subscriptions(Organization, Subscription, Plan), 0
        )

    def test_backfill_without_default_plan_does_nothing(self):
        OrganizationFactory(subscription=False)
        Plan.objects.filter(is_default=True).update(is_default=False)
        PlanFactory(code='other')
        self.assertEqual(
            create_courtesy_subscriptions(Organization, Subscription, Plan), 0
        )

    def test_command(self):
        OrganizationFactory(subscription=False)
        out = StringIO()
        call_command('ensure_subscriptions', stdout=out)
        self.assertIn('1 subscription(s) created.', out.getvalue())
        self.assertFalse(
            Organization.objects.filter(subscription__isnull=True).exists()
        )
