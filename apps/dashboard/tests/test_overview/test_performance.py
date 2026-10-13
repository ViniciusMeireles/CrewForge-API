from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory

QUERY_BUDGET = 11


class OverviewPerformanceTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.url = reverse('dashboard:overview')
        self.organization = self.new_account()
        self.member = self.organization.owner
        self.client.get(self.url)

    def _query_count(self):
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        return len(context.captured_queries)

    def test_query_count_is_constant_and_within_budget(self):
        small = self._query_count()

        for _ in range(10):
            MemberFactory(
                organization=self.organization,
                role=MemberRoleChoices.MEMBER,
            )
            team = TeamFactory(organization=self.organization)
            TeamMemberFactory(
                organization=self.organization,
                team=team,
                member=self.member,
            )
            InvitationFactory(
                organization=self.organization,
                role=MemberRoleChoices.MEMBER,
                expired_at=timezone.now() + timedelta(days=3),
            )

        large = self._query_count()
        self.assertEqual(small, large)
        self.assertLessEqual(small, QUERY_BUDGET)
