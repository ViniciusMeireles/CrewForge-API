from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.models.audit_event import AuditEvent
from apps.billing.choices import SubscriptionCourtesyChoices, SubscriptionStatusChoices
from apps.billing.factories.plans import PlanFactory
from apps.billing.models.plan import Plan
from apps.billing.models.subscription import Subscription
from apps.platform.tests.mixins import PlatformTestMixin


class PlatformChangePlanTestCase(PlatformTestMixin, APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.free = Plan.objects.get(code='free')
        self.pro = Plan.objects.get(code='pro')
        Subscription.objects.filter(organization=self.organization).update(
            plan=self.free
        )
        self.url = reverse(
            'platform:organizations-change-plan', args=[self.organization.id]
        )

    def post(self, data):
        return self.client.post(self.url, data=data, format='json')

    def test_admin_changes_plan(self):
        staff = self.authenticate_staff('admin')
        response = self.post({'plan': self.pro.id, 'reason': '  Sales deal  '})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            response.data['subscription'],
            {
                'plan': {'id': self.pro.id, 'code': 'pro', 'name': 'Pro'},
                'status': 'active',
                'is_complimentary': True,
                'trial_ends_at': None,
            },
        )
        subscription = Subscription.objects.get(organization=self.organization)
        self.assertEqual(subscription.plan, self.pro)
        self.assertEqual(subscription.status, SubscriptionStatusChoices.ACTIVE)
        self.assertIsNone(subscription.cycle)
        self.assertEqual(subscription.courtesy, SubscriptionCourtesyChoices.PLATFORM)
        event = AuditEvent.objects.get(
            action=AuditActionChoices.PLATFORM_SUBSCRIPTION_PLAN_CHANGED
        )
        self.assertEqual(event.organization_id, self.organization.id)
        self.assertEqual(event.actor_type, AuditActorTypeChoices.PLATFORM)
        self.assertEqual(event.actor_user, staff)
        self.assertEqual(event.metadata, {'reason': 'Sales deal'})
        self.assertEqual(
            event.changes,
            [
                {'field': 'plan', 'before': 'free', 'after': 'pro'},
                {'field': 'courtesy', 'before': '', 'after': 'platform'},
            ],
        )

    def test_trial_becomes_active(self):
        self.authenticate_staff('admin')
        Subscription.objects.filter(organization=self.organization).update(
            plan=self.pro, status='trialing', trial_ends_at='2030-01-01T00:00:00Z'
        )
        other = PlanFactory()
        self.assertEqual(
            self.post({'plan': other.id, 'reason': 'Deal'}).status_code,
            http_status.HTTP_200_OK,
        )
        subscription = Subscription.objects.get(organization=self.organization)
        self.assertEqual(subscription.status, SubscriptionStatusChoices.ACTIVE)
        self.assertIsNone(subscription.trial_ends_at)

    def test_free_plan_has_no_courtesy(self):
        self.authenticate_staff('admin')
        Subscription.objects.filter(organization=self.organization).update(
            plan=self.pro, courtesy='legacy'
        )
        self.post({'plan': self.free.id, 'reason': 'Downgrade'})
        self.assertEqual(
            Subscription.objects.get(organization=self.organization).courtesy, ''
        )

    def test_support_forbidden(self):
        self.authenticate_staff('support')
        response = self.post({'plan': self.pro.id, 'reason': 'Deal'})
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            Subscription.objects.get(organization=self.organization).plan, self.free
        )

    def test_same_plan_400(self):
        self.authenticate_staff('admin')
        response = self.post({'plan': self.free.id, 'reason': 'Deal'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            [str(message) for message in response.data['error']['details']['plan']],
            ['The organization is already on this plan.'],
        )

    def test_reason_required(self):
        self.authenticate_staff('admin')
        for reason in ('', '   ', 'x' * 501):
            with self.subTest(length=len(reason)):
                response = self.post({'plan': self.pro.id, 'reason': reason})
                self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
                self.assertIn('reason', response.data['error']['details'])

    def test_inactive_plan_400(self):
        self.authenticate_staff('admin')
        retired = PlanFactory(is_active=False)
        response = self.post({'plan': retired.id, 'reason': 'Deal'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_deleted_organization_409(self):
        self.authenticate_staff('admin')
        self.organization.is_active = False
        self.organization.save(update_fields=['is_active'])
        response = self.post({'plan': self.pro.id, 'reason': 'Deal'})
        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)

    def test_unknown_organization_404(self):
        self.authenticate_staff('admin')
        response = self.client.post(
            reverse('platform:organizations-change-plan', args=[999999]),
            data={'plan': self.pro.id, 'reason': 'Deal'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_missing_subscription_is_created(self):
        self.authenticate_staff('admin')
        Subscription.objects.filter(organization=self.organization).delete()
        response = self.post({'plan': self.pro.id, 'reason': 'Repair'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        subscription = Subscription.objects.get(organization=self.organization)
        self.assertEqual(subscription.plan, self.pro)
        event = AuditEvent.objects.get(
            action=AuditActionChoices.PLATFORM_SUBSCRIPTION_PLAN_CHANGED
        )
        self.assertEqual(
            event.changes[0], {'field': 'plan', 'before': None, 'after': 'pro'}
        )

    def test_detail_includes_subscription(self):
        self.authenticate_staff('support')
        response = self.client.get(
            reverse('platform:organizations-detail', args=[self.organization.id])
        )
        self.assertEqual(response.data['subscription']['plan']['code'], 'free')
