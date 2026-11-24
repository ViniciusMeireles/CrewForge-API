from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.factories.organizations import OrganizationFactory
from apps.billing.choices import BillingCycleChoices, SubscriptionStatusChoices
from apps.billing.factories.plans import PlanFactory, SubscriptionFactory
from apps.billing.models.plan import Plan
from apps.billing.models.subscription import Subscription


class PlanConstraintsTestCase(TestCase):
    def assert_integrity_error(self, **fields):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlanFactory(**fields)

    def test_single_default_and_free_plan(self):
        self.assert_integrity_error(is_default=True, trial_days=7)
        self.assert_integrity_error(
            is_free=True, monthly_price=Decimal('0'), annual_price=Decimal('0')
        )

    def test_free_plan_costs_nothing(self):
        Plan.objects.filter(is_free=True).update(is_free=False)
        self.assert_integrity_error(is_free=True, monthly_price=Decimal('1.00'))

    def test_default_plan_has_a_trial(self):
        Plan.objects.filter(is_default=True).update(is_default=False)
        self.assert_integrity_error(is_default=True, trial_days=0)

    def test_prices_not_negative(self):
        self.assert_integrity_error(monthly_price=Decimal('-1.00'))
        self.assert_integrity_error(extra_seat_price=Decimal('-1.00'))

    def test_clean_validates_entitlements(self):
        plan = PlanFactory.build(entitlements={'unknown': 1})
        with self.assertRaises(ValidationError):
            plan.clean()

    def test_offered_excludes_inactive_and_private(self):
        PlanFactory(code='hidden', is_public=False)
        PlanFactory(code='retired', is_active=False)
        codes = list(Plan.objects.offered().values_list('code', flat=True))
        self.assertEqual(codes[:2], ['free', 'pro'])
        self.assertNotIn('hidden', codes)
        self.assertNotIn('retired', codes)

    def test_plan_in_use_is_protected(self):
        subscription = SubscriptionFactory()
        with self.assertRaises(ProtectedError):
            subscription.plan.delete()


class SubscriptionTestCase(TestCase):
    def test_trial_needs_an_end(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SubscriptionFactory(status=SubscriptionStatusChoices.TRIALING)

    def test_one_subscription_per_organization(self):
        organization = OrganizationFactory()
        with self.assertRaises(IntegrityError), transaction.atomic():
            SubscriptionFactory(organization=organization)

    def test_is_complimentary(self):
        pro = Plan.objects.get(code='pro')
        free = Plan.objects.get(code='free')
        cases = [
            (pro, SubscriptionStatusChoices.ACTIVE, None, True),
            (pro, SubscriptionStatusChoices.ACTIVE, BillingCycleChoices.MONTHLY, False),
            (free, SubscriptionStatusChoices.ACTIVE, None, False),
            (pro, SubscriptionStatusChoices.TRIALING, None, False),
        ]
        for plan, status, cycle, expected in cases:
            with self.subTest(plan=plan.code, status=status, cycle=cycle):
                subscription = Subscription(
                    plan=plan,
                    status=status,
                    cycle=cycle,
                    trial_ends_at=timezone.now(),
                )
                self.assertIs(subscription.is_complimentary, expected)
