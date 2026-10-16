from unittest.mock import patch

from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.audit.choices import AuditActionChoices
from apps.audit.tests.test_recording.test_accounts import AuditRecordingTestMixin
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory
from apps.teams.models.team import Team


class TeamRecordingTestCase(AuditRecordingTestMixin, APITestCase):
    def test_team_lifecycle(self):
        response = self.client.post(
            reverse('teams:teams-list'),
            {'name': 'Design', 'description': 'UI'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        created = self.assert_single(
            AuditActionChoices.TEAM_CREATED,
            organization_id=self.organization.pk,
            actor_member=self.owner,
            target_type='team',
            target_label='Design',
        )
        self.assertEqual(self.changed(created)['name'], (None, 'Design'))
        detail = reverse('teams:teams-detail', args=[response.data['id']])
        self.client.put(detail, {'name': 'Product', 'description': 'UI'}, format='json')
        updated = self.assert_single(AuditActionChoices.TEAM_UPDATED)
        self.assertIn(('Design', 'Product'), self.changed(updated).values())
        self.client.delete(detail)
        self.assert_single(AuditActionChoices.TEAM_DELETED, target_label='Product')

    def test_failed_create_records_nothing(self):
        response = self.client.post(
            reverse('teams:teams-list'), {'name': '!!!'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertFalse(self.events().exists())

    def test_event_failure_rolls_back_the_write(self):
        team = TeamFactory(organization=self.organization)
        with patch(
            'apps.audit.models.audit_event.AuditEvent.objects.create',
            side_effect=RuntimeError('audit down'),
        ):
            response = self.client.delete(reverse('teams:teams-detail', args=[team.pk]))
        self.assertEqual(
            response.status_code, http_status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        self.assertTrue(Team.objects.get(pk=team.pk).is_active)


class TeamMemberRecordingTestCase(AuditRecordingTestMixin, APITestCase):
    def test_team_member_lifecycle(self):
        team = TeamFactory(organization=self.organization)
        member = MemberFactory(organization=self.organization)
        response = self.client.post(
            reverse('teams:team_members-list'),
            {
                'team': team.pk,
                'member': member.pk,
                'role': TeamMemberRoleChoices.MEMBER,
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        added = self.assert_single(
            AuditActionChoices.TEAM_MEMBER_ADDED,
            organization_id=self.organization.pk,
            target_type='team_member',
        )
        self.assertEqual(added.target_label, f'{member.audit_label} - {team.name}')
        detail = reverse('teams:team_members-detail', args=[response.data['id']])
        self.client.put(
            detail,
            {'team': team.pk, 'member': member.pk, 'role': TeamMemberRoleChoices.ADMIN},
            format='json',
        )
        updated = self.assert_single(AuditActionChoices.TEAM_MEMBER_UPDATED)
        self.assertEqual(self.changed(updated)['role'], ('member', 'admin'))
        self.client.delete(detail)
        self.assert_single(AuditActionChoices.TEAM_MEMBER_REMOVED)

    def test_refused_last_owner_removal_records_nothing(self):
        owner = TeamMemberFactory(
            team=TeamFactory(organization=self.organization),
            member=MemberFactory(organization=self.organization),
            role=TeamMemberRoleChoices.OWNER,
        )
        response = self.client.delete(
            reverse('teams:team_members-detail', args=[owner.pk])
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertFalse(self.events().exists())
