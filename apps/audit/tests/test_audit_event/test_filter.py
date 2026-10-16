import datetime

from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.audit.choices import AuditActionChoices
from apps.audit.factories.audit_event import AuditEventFactory
from apps.audit.tests.mixins import AuditAPITestCaseMixin


class AuditEventFilterTestCase(AuditAPITestCaseMixin, APITestCase):
    def create_event(self, **kwargs):
        kwargs.setdefault('actor_member', self.owner)
        return AuditEventFactory(organization=self.organization, **kwargs)

    def ids(self, **params):
        response = self.list_events(**params)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK, response.data)
        return {item['id'] for item in response.data['results']}

    def test_filter_period(self):
        now = timezone.now()
        old = self.create_event(created_at=now - datetime.timedelta(days=10))
        recent = self.create_event(created_at=now)
        today = now.date().isoformat()
        self.assertEqual(self.ids(created_at_after=today), {recent.pk})
        before = (now - datetime.timedelta(days=5)).date().isoformat()
        self.assertEqual(self.ids(created_at_before=before), {old.pk})
        self.assertEqual(
            self.ids(created_at_after=today, created_at_before=today), {recent.pk}
        )

    def test_filter_inverted_period(self):
        response = self.list_events(
            created_at_after='2026-10-10', created_at_before='2026-10-01'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_filter_actor(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        by_admin = self.create_event(actor_member=admin)
        self.create_event()
        self.assertEqual(self.ids(actor=admin.pk), {by_admin.pk})

    def test_filter_action_in(self):
        created = self.create_event(action=AuditActionChoices.TEAM_CREATED)
        removed = self.create_event(action=AuditActionChoices.MEMBER_REMOVED)
        self.create_event(action=AuditActionChoices.TEAM_UPDATED)
        self.assertEqual(
            self.ids(action__in='team.created,member.removed'),
            {created.pk, removed.pk},
        )

    def test_filter_target_type_in(self):
        team = self.create_event(target_type='team')
        member = self.create_event(target_type='member')
        self.create_event(target_type='invitation')
        self.assertEqual(self.ids(target_type__in='team,member'), {team.pk, member.pk})

    def test_filter_target_id(self):
        target = self.create_event(target_type='team', target_id='42')
        self.create_event(target_type='team', target_id='43')
        self.assertEqual(self.ids(target_type='team', target_id='42'), {target.pk})

    def test_filter_target_id_requires_target_type(self):
        response = self.list_events(target_id='42')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_filter_options(self):
        removed = MemberFactory(organization=self.organization, is_active=False)
        MemberFactory()
        response = self.client.get(reverse('audit:audit_events-filter-options'))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('action', response.data)
        actors = {option['value'] for option in response.data['actor']['results']}
        self.assertIn(self.owner.pk, actors)
        self.assertNotIn(removed.pk, actors)
        self.assertEqual(len(actors), 1)

    def test_filter_options_require_audit_access(self):
        member = MemberFactory(organization=self.organization)
        self.client.force_authenticate(member=member)
        response = self.client.get(reverse('audit:audit_events-filter-options'))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
