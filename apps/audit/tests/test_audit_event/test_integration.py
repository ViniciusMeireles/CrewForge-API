from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.audit.tests.mixins import AuditAPITestCaseMixin
from apps.teams.factories.teams import TeamFactory


class AuditEventIntegrationTestCase(AuditAPITestCaseMixin, APITestCase):
    def test_role_change_is_listed_with_its_diff(self):
        member = MemberFactory(organization=self.organization)
        response = self.client.patch(
            reverse('accounts:members-update-role', args=[member.pk]),
            {'role': MemberRoleChoices.MANAGER},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        results = self.list_events(action='member.role_changed').data['results']
        self.assertEqual(len(results), 1)
        event = results[0]
        self.assertEqual(event['actor']['member_id'], self.owner.pk)
        self.assertEqual(event['target_id'], str(member.pk))
        self.assertEqual(
            [(c['field'], c['before'], c['after']) for c in event['changes']],
            [('role', 'member', 'manager')],
        )

    def test_label_survives_the_soft_delete(self):
        team = TeamFactory(organization=self.organization, name='Design')
        response = self.client.delete(reverse('teams:teams-detail', args=[team.pk]))
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        team.refresh_from_db()
        team.name = 'Renamed'
        team.save()
        event = self.list_events(action='team.deleted').data['results'][0]
        self.assertEqual(event['target_label'], 'Design')

    def test_list_query_count_is_constant(self):
        for _ in range(3):
            TeamFactory(organization=self.organization)
        self.clear_events()
        for name in ('A', 'B', 'C'):
            self.client.post(
                reverse('teams:teams-list'),
                {'name': f'Team {name}', 'slug': f'team-{name.lower()}'},
                format='json',
            )
        with self.assertNumQueries(self.list_queries()):
            self.list_events()

    def list_queries(self) -> int:
        with CaptureQueriesContext(connection) as context:
            self.list_events(page_size=1)
        return len(context.captured_queries)
