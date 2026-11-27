from datetime import UTC, datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.accounts.factories.organizations import OrganizationFactory
from apps.billing import pricing
from apps.billing.factories.plans import PlanFactory
from apps.billing.models.subscription import Subscription
from apps.billing.tests.helpers import free_plan, pro_plan

NOW = datetime(2026, 11, 26, 12, tzinfo=UTC)


class ClassifyTestCase(TestCase):
    def setUp(self):
        self.subscription = Subscription.objects.get(organization=OrganizationFactory())
        self.cheap = PlanFactory(
            monthly_price=Decimal('49.00'), annual_price=Decimal('490.00')
        )

    def paid(self, plan, cycle):
        self.subscription.plan = plan
        self.subscription.cycle = cycle
        self.subscription.current_period_start = NOW - timedelta(days=15)
        self.subscription.current_period_end = NOW + timedelta(days=15)

    def test_free_trial_or_courtesy_is_new(self):
        self.assertEqual(
            pricing.classify(self.subscription, pro_plan(), 'monthly'), 'new'
        )

    def test_upgrades(self):
        self.paid(self.cheap, 'monthly')
        self.assertEqual(
            pricing.classify(self.subscription, pro_plan(), 'monthly'), 'upgrade'
        )
        self.paid(pro_plan(), 'monthly')
        self.assertEqual(
            pricing.classify(self.subscription, pro_plan(), 'annual'), 'upgrade'
        )

    def test_downgrades(self):
        self.paid(pro_plan(), 'monthly')
        self.assertEqual(
            pricing.classify(self.subscription, self.cheap, 'monthly'), 'downgrade'
        )
        self.paid(pro_plan(), 'annual')
        self.assertEqual(
            pricing.classify(self.subscription, pro_plan(), 'monthly'), 'downgrade'
        )

    def test_same_plan_free_plan_and_unpriced_cycle_are_refused(self):
        self.paid(pro_plan(), 'monthly')
        unpriced = PlanFactory(annual_price=None)
        for plan, cycle in (
            (pro_plan(), 'monthly'),
            (free_plan(), 'monthly'),
            (unpriced, 'annual'),
        ):
            with (
                self.subTest(plan=plan.code, cycle=cycle),
                self.assertRaises(ValidationError),
            ):
                pricing.classify(self.subscription, plan, cycle)


class ProrationTestCase(TestCase):
    def setUp(self):
        self.subscription = Subscription.objects.get(organization=OrganizationFactory())
        self.hundred = PlanFactory(
            monthly_price=Decimal('100.00'), annual_price=Decimal('1000.00')
        )
        self.two_hundred = PlanFactory(
            monthly_price=Decimal('200.00'), annual_price=Decimal('2000.00')
        )
        self.subscription.plan = self.hundred
        self.subscription.cycle = 'monthly'
        self.subscription.current_period_start = NOW - timedelta(days=15)
        self.subscription.current_period_end = NOW + timedelta(days=15)

    def test_ac12_half_period_left(self):
        self.assertEqual(
            pricing.proration(self.subscription, self.two_hundred, 'monthly', NOW),
            Decimal('50.00'),
        )

    def test_period_edges(self):
        start = self.subscription.current_period_start
        end = self.subscription.current_period_end
        self.assertEqual(
            pricing.proration(self.subscription, self.two_hundred, 'monthly', start),
            Decimal('100.00'),
        )
        self.assertEqual(
            pricing.proration(self.subscription, self.two_hundred, 'monthly', end),
            Decimal('0.00'),
        )

    def test_annual_switch_credits_the_unused_month(self):
        self.assertEqual(
            pricing.proration(self.subscription, self.hundred, 'annual', NOW),
            Decimal('950.00'),
        )


class PeriodEndTestCase(TestCase):
    def test_month_ends_and_years(self):
        self.assertEqual(
            pricing.period_end(datetime(2026, 1, 31, tzinfo=UTC), 'monthly'),
            datetime(2026, 2, 28, tzinfo=UTC),
        )
        self.assertEqual(
            pricing.period_end(datetime(2026, 12, 15, tzinfo=UTC), 'monthly'),
            datetime(2027, 1, 15, tzinfo=UTC),
        )
        self.assertEqual(
            pricing.period_end(datetime(2028, 2, 29, tzinfo=UTC), 'annual'),
            datetime(2029, 2, 28, tzinfo=UTC),
        )
