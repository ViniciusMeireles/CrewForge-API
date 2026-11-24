from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.users import UserFactory
from apps.accounts.models.organization import Organization
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.audit.choices import AuditActionChoices
from apps.audit.models.audit_event import AuditEvent
from apps.billing.choices import SubscriptionStatusChoices
from apps.billing.models.subscription import Subscription
from apps.billing.tests.helpers import set_plan


class StartSubscriptionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('accounts:organizations-list')

    def create(self, slug: str) -> Organization:
        response = self.client.post(
            self.url, data={'name': slug.title(), 'slug': slug}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        return Organization.objects.get(pk=response.data['id'])

    def test_first_organization_starts_trial(self):
        before = timezone.now()
        organization = self.create('acme')
        subscription = Subscription.objects.get(organization=organization)
        self.assertEqual(subscription.status, SubscriptionStatusChoices.TRIALING)
        self.assertEqual(subscription.plan.code, 'pro')
        self.assertIsNone(subscription.cycle)
        self.assertGreaterEqual(subscription.trial_ends_at, before + timedelta(days=14))
        self.assertLessEqual(
            subscription.trial_ends_at, timezone.now() + timedelta(days=14)
        )

    def test_trial_started_event(self):
        organization = self.create('acme')
        event = AuditEvent.objects.get(
            action=AuditActionChoices.BILLING_SUBSCRIPTION_TRIAL_STARTED
        )
        self.assertEqual(event.organization_id, organization.pk)
        self.assertEqual(event.actor_user, self.user)
        self.assertEqual(event.metadata['plan'], 'pro')

    def test_second_organization_starts_free(self):
        self.create('acme')
        second = self.create('globex')
        subscription = Subscription.objects.get(organization=second)
        self.assertEqual(subscription.status, SubscriptionStatusChoices.ACTIVE)
        self.assertEqual(subscription.plan.code, 'free')
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditActionChoices.BILLING_SUBSCRIPTION_TRIAL_STARTED
            ).count(),
            1,
        )

    def test_soft_deleted_trial_still_counts(self):
        first = self.create('acme')
        Organization.objects.filter(pk=first.pk).update(is_active=False)
        second = self.create('globex')
        self.assertEqual(second.subscription.plan.code, 'free')

    def test_another_owner_trial_does_not_count(self):
        other = UserFactory()
        self.client.force_authenticate(user=other)
        self.create('acme')
        self.client.force_authenticate(user=self.user)
        self.assertEqual(
            self.create('globex').subscription.status,
            SubscriptionStatusChoices.TRIALING,
        )

    def test_past_trial_stays_trialing(self):
        organization = self.create('acme')
        Subscription.objects.filter(organization=organization).update(
            trial_ends_at=timezone.now() - timedelta(days=3)
        )
        set_plan(organization, max_teams=10)
        organization.refresh_from_db()
        subscription = Subscription.objects.get(organization=organization)
        self.assertEqual(subscription.status, SubscriptionStatusChoices.TRIALING)


class SignupStartsTrialTestCase(APITestCaseMixin, APITestCase):
    def test_signup_starts_a_trial(self):
        data = UserFactory.build()
        response = self.client.post(
            reverse('accounts:signup-list'),
            data={
                'user': {
                    'username': data.username,
                    'email': data.email,
                    'first_name': data.first_name,
                    'last_name': data.last_name,
                    'password': 'A-strong-pass-123',
                },
                'organization': {'name': 'Acme', 'slug': 'acme-signup'},
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        organization = Organization.objects.get(slug='acme-signup')
        subscription = Subscription.objects.get(organization=organization)
        self.assertEqual(subscription.status, SubscriptionStatusChoices.TRIALING)
        self.assertEqual(subscription.plan.code, 'pro')
        event = AuditEvent.objects.get(
            action=AuditActionChoices.BILLING_SUBSCRIPTION_TRIAL_STARTED
        )
        self.assertEqual(event.organization_id, organization.pk)
        self.assertEqual(event.actor_user.email, data.email)
