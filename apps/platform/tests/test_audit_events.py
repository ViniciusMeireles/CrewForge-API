from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.audit.factories.audit_event import AuditEventFactory
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
