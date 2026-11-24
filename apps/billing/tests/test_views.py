from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.audit.choices import AuditActionChoices
from apps.audit.models.audit_event import AuditEvent
from apps.billing.choices import SubscriptionStatusChoices
from apps.billing.entitlements import BYTES_PER_MB
from apps.billing.factories.plans import PlanFactory
from apps.billing.models.plan import Plan
from apps.billing.models.subscription import Subscription
from apps.billing.tests.helpers import set_plan
from apps.teams.factories.teams import TeamFactory


class SubscriptionViewTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        Subscription.objects.filter(organization=self.organization).update(
            plan=Plan.objects.get(code='free')
        )
        self.url = reverse('billing:subscription')

    def as_role(self, role):
        member = (
            self.organization.owner
            if role == MemberRoleChoices.OWNER
            else MemberFactory(organization=self.organization, role=role)
        )
        self.client.force_authenticate(member=member)

    def test_owner_and_admin_read(self):
        TeamFactory(organization=self.organization)
        for role in (MemberRoleChoices.OWNER, MemberRoleChoices.ADMIN):
            with self.subTest(role=role):
                self.as_role(role)
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, http_status.HTTP_200_OK)
                self.assertEqual(response.data['plan']['code'], 'free')
                self.assertEqual(response.data['status'], 'active')
                self.assertFalse(response.data['is_complimentary'])
                self.assertEqual(
                    response.data['usage']['teams'], {'current': 1, 'max': 1}
                )
                self.assertEqual(
                    response.data['usage']['storage'],
                    {'current': 0, 'max': 100 * BYTES_PER_MB},
                )
                self.assertEqual(response.data['usage']['members']['max'], 3)

    def test_manager_and_member_forbidden(self):
        for role in (MemberRoleChoices.MANAGER, MemberRoleChoices.MEMBER):
            with self.subTest(role=role):
                self.as_role(role)
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
                self.assertEqual(response.data['error']['code'], 'PERMISSION_DENIED')

    def test_needs_organization_context(self):
        self.client.force_authenticate(user=self.organization.owner.user)
        self.assertEqual(
            self.client.get(self.url).status_code, http_status.HTTP_403_FORBIDDEN
        )

    def test_anonymous(self):
        self.assertEqual(
            self.client.get(self.url).status_code, http_status.HTTP_401_UNAUTHORIZED
        )

    def test_only_the_session_organization(self):
        other = OrganizationFactory()
        TeamFactory.create_batch(3, organization=other)
        self.as_role(MemberRoleChoices.OWNER)
        self.assertEqual(self.client.get(self.url).data['usage']['teams']['current'], 0)

    def test_complimentary_and_unlimited(self):
        Subscription.objects.filter(organization=self.organization).update(
            plan=Plan.objects.get(code='pro'), courtesy='legacy'
        )
        set_plan(self.organization, max_teams=None)
        Subscription.objects.filter(organization=self.organization).update(
            plan=Plan.objects.get(code='pro')
        )
        self.as_role(MemberRoleChoices.OWNER)
        data = self.client.get(self.url).data
        self.assertTrue(data['is_complimentary'])
        self.assertEqual(
            data['plan']['entitlements']['storage_bytes'], 5120 * BYTES_PER_MB
        )


class PlanListViewTestCase(APITestCaseMixin, APITestCase):
    url = reverse('billing:plans')

    def test_offered_plans_without_organization_context(self):
        PlanFactory(code='hidden', is_public=False)
        PlanFactory(code='retired', is_active=False)
        self.client.force_authenticate(user=UserFactory())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual([plan['code'] for plan in response.data], ['free', 'pro'])
        pro = response.data[1]
        self.assertEqual(pro['monthly_price'], '99.00')
        self.assertEqual(pro['currency'], 'BRL')
        self.assertEqual(
            pro['entitlements'],
            {
                'max_members': 25,
                'max_teams': 10,
                'storage_bytes': 5120 * BYTES_PER_MB,
                'audit': True,
                'audit_retention_days': 365,
            },
        )

    def test_anonymous(self):
        self.assertEqual(
            self.client.get(self.url).status_code, http_status.HTTP_401_UNAUTHORIZED
        )


class AuditGateTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        set_plan(self.organization, audit=False)
        self.url = reverse('audit:audit_events-list')

    def test_free_plan_hides_audit(self):
        session = self.client.get(reverse('accounts:session')).data
        self.assertFalse(session['member']['access']['audit'])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['code'], 'PLAN_FEATURE_UNAVAILABLE')

    def test_member_role_keeps_permission_denied(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        self.assertEqual(
            self.client.get(self.url).data['error']['code'], 'PERMISSION_DENIED'
        )

    def test_events_recorded_without_feature(self):
        self.client.post(reverse('teams:teams-list'), {'name': 'Ops'}, format='json')
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization, action=AuditActionChoices.TEAM_CREATED
            ).exists()
        )

    def test_upgrade_reveals_history(self):
        set_plan(self.organization, audit=True)
        self.assertEqual(self.client.get(self.url).status_code, http_status.HTTP_200_OK)


class SessionSubscriptionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.url = reverse('accounts:session')

    def test_owner_and_admin_get_the_summary(self):
        for member in (
            self.organization.owner,
            MemberFactory(organization=self.organization, role=MemberRoleChoices.ADMIN),
        ):
            with self.subTest(role=member.role):
                self.client.force_authenticate(member=member)
                data = self.client.get(self.url).data
                self.assertTrue(data['member']['access']['billing'])
                self.assertEqual(
                    set(data['subscription']),
                    {'status', 'plan', 'trial_ends_at', 'is_complimentary'},
                )
                self.assertEqual(
                    data['subscription']['status'], SubscriptionStatusChoices.ACTIVE
                )

    def test_manager_and_member_get_none(self):
        for role in (MemberRoleChoices.MANAGER, MemberRoleChoices.MEMBER):
            with self.subTest(role=role):
                member = MemberFactory(organization=self.organization, role=role)
                self.client.force_authenticate(member=member)
                data = self.client.get(self.url).data
                self.assertFalse(data['member']['access']['billing'])
                self.assertIsNone(data['subscription'])

    def test_no_organization_context(self):
        self.client.force_authenticate(user=self.organization.owner.user)
        self.assertIsNone(self.client.get(self.url).data['subscription'])
