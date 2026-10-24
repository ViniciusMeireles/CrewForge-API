from unittest import mock

from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.audit.choices import AuditActorTypeChoices
from apps.audit.factories.audit_event import AuditEventFactory
from apps.audit.models.audit_event import AuditEvent
from apps.platform.tests.mixins import PlatformTestMixin


class PlatformAuditEventTestCase(PlatformTestMixin, APITestCaseMixin, APITestCase):
    def setUp(self):
        self.list_url = reverse('platform:audit_events-list')
        self.organization_event = AuditEventFactory()
        self.account_event = AuditEventFactory(account=True)
        self.authenticate_staff()

    def ids(self, **params):
        response = self.client.get(self.list_url, data=params)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        return {row['id'] for row in response.data['results']}

    def test_lists_organization_and_account_events(self):
        self.assertEqual(
            self.ids(), {self.organization_event.id, self.account_event.id}
        )

    def test_organization_payload(self):
        response = self.client.get(self.list_url, data={'scope': 'organization'})
        row = response.data['results'][0]
        self.assertEqual(
            row['organization'],
            {
                'id': self.organization_event.organization_id,
                'name': self.organization_event.organization.name,
            },
        )

    def test_scope_and_organization_filters(self):
        self.assertEqual(self.ids(scope='account'), {self.account_event.id})
        self.assertEqual(
            self.ids(organization=self.organization_event.organization_id),
            {self.organization_event.id},
        )

    def test_user_filter_matches_actor_or_subject(self):
        subject = UserFactory()
        event = AuditEventFactory(account=True, subject_user=subject)
        self.assertEqual(self.ids(user=subject.id), {event.id})

    def test_inverted_period_is_refused(self):
        response = self.client.get(
            self.list_url,
            data={'created_at_after': '2026-10-20', 'created_at_before': '2026-10-01'},
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)


class PlatformAuditEventFilterOptionsTestCase(
    PlatformTestMixin, APITestCaseMixin, APITestCase
):
    def setUp(self):
        self.url = reverse('platform:audit_events-filter-options')

    def test_staff_gets_action_and_record_type_options(self):
        self.authenticate_staff()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        actions = {option['value'] for option in response.data['action__in']}
        self.assertIn('user.platform_role_changed', actions)
        self.assertIn('member.role_changed', actions)

    def test_organization_options_match_part_of_the_name_ignoring_accents(self):
        OrganizationFactory(name='Açaí Labs')
        OrganizationFactory(name='Globex Corp')
        self.authenticate_staff()
        response = self.client.get(self.url, {'organization': 'acai'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        labels = [o['label'] for o in response.data['organization']['results']]
        self.assertEqual(labels, ['Açaí Labs'])

    def test_role_none_is_forbidden(self):
        self.client.force_authenticate(user=UserFactory())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)


class PlatformActionAuditTestCase(PlatformTestMixin, APITestCaseMixin, APITestCase):
    def test_every_staff_action_audited(self):
        staff = self.authenticate_staff('admin')
        organization = OrganizationFactory()
        new_owner = MemberFactory(organization=organization)
        user = UserFactory(email_verified_at=None)
        steps = [
            ('organizations-suspend', organization.id, {}, 'organization.suspended'),
            (
                'organizations-reactivate',
                organization.id,
                {},
                'organization.reactivated',
            ),
            (
                'organizations-transfer-ownership',
                organization.id,
                {'member': new_owner.id},
                'organization.ownership_transferred',
            ),
            ('users-resend-verification', user.id, {}, 'user.verification_resent'),
            ('users-block', user.id, {}, 'user.blocked'),
            ('users-unblock', user.id, {}, 'user.unblocked'),
            ('users-end-sessions', user.id, {}, 'user.sessions_ended'),
            ('users-force-password-reset', user.id, {}, 'user.password_reset_forced'),
        ]
        with mock.patch('apps.accounts.tasks.send_email_task.apply_async'):
            for name, pk, data, action in steps:
                with self.subTest(action=action):
                    reason = f'Reason for {action}'
                    response = self.client.post(
                        reverse(f'platform:{name}', args=[pk]),
                        data={**data, 'reason': reason},
                        format='json',
                    )
                    self.assertEqual(response.status_code, http_status.HTTP_200_OK)
                    event = AuditEvent.objects.get(action=action)
                    self.assertEqual(event.actor_type, AuditActorTypeChoices.PLATFORM)
                    self.assertEqual(event.actor_user_id, staff.id)
                    self.assertEqual(event.metadata, {'reason': reason})
                    if action.startswith('organization.'):
                        self.assertEqual(event.organization_id, organization.id)
                    else:
                        self.assertIsNone(event.organization_id)
                        self.assertEqual(event.subject_user_id, user.id)
        self.assertEqual(
            set(AuditEvent.objects.values_list('action', flat=True)),
            {step[3] for step in steps},
        )
