from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.models.member import Member
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory
from apps.teams.models.team_member import TeamMember


class TeamMemberRemovedMemberTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.member = MemberFactory(organization=self.organization)
        self.other = MemberFactory(organization=self.organization)
        self.teams = [TeamFactory(organization=self.organization) for _ in range(2)]
        for team in self.teams:
            TeamMemberFactory(team=team, member=self.member)
            TeamMemberFactory(team=team, member=self.other)

    def _remove(self, member):
        url = reverse('accounts:members-detail', args=[member.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_removing_a_member_ends_their_team_memberships(self):
        self._remove(self.member)
        self.assertFalse(
            TeamMember.objects.filter(member=self.member, is_active=True).exists(),
        )

    def test_other_members_keep_their_team_memberships(self):
        self._remove(self.member)
        self.assertEqual(
            TeamMember.objects.filter(member=self.other, is_active=True).count(),
            2,
        )

    def test_readmission_does_not_restore_team_memberships(self):
        self._remove(self.member)
        Member.objects.admit(
            user=self.member.user,
            organization=self.organization,
            role=self.member.role,
        )
        self.assertFalse(
            TeamMember.objects.filter(member=self.member, is_active=True).exists(),
        )
