from unittest.mock import patch

from django.test import RequestFactory, TestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.users import UserFactory
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.services import (
    diff_instance,
    label_for,
    model_for_target_type,
    record_audit_event,
    snapshot_instance,
    target_type_for,
)
from apps.teams.factories.team_members import TeamMemberFactory
from apps.teams.factories.teams import TeamFactory
from apps.teams.models.team_member import TeamMember


class AuditServicesTestCase(TestCase):
    def test_snapshot_skips_bookkeeping_and_secrets(self):
        snapshot = snapshot_instance(UserFactory())
        for name in ('id', 'created_at', 'updated_at', 'password', 'last_login'):
            self.assertNotIn(name, snapshot)
        self.assertNotIn('full_name', snapshot)
        self.assertIn('first_name', snapshot)

    def test_snapshot_relations_use_labels(self):
        member = MemberFactory()
        snapshot = snapshot_instance(member)
        self.assertEqual(
            snapshot['organization'],
            {'id': member.organization_id, 'label': member.organization.name},
        )

    def test_diff_returns_only_changed_fields(self):
        team = TeamFactory(name='Old')
        before = snapshot_instance(team)
        team.name = 'New'
        self.assertEqual(
            diff_instance(before, team),
            [{'field': 'name', 'before': 'Old', 'after': 'New'}],
        )

    def test_diff_exclude(self):
        team = TeamFactory(name='Old')
        before = snapshot_instance(team, exclude=('name',))
        team.name = 'New'
        self.assertEqual(diff_instance(before, team, exclude=('name',)), [])

    def test_target_type(self):
        self.assertEqual(target_type_for(TeamMemberFactory()), 'team_member')
        self.assertIs(model_for_target_type('team_member'), TeamMember)
        self.assertIsNone(model_for_target_type('nothing'))

    def test_labels(self):
        member = MemberFactory(nickname='nick')
        self.assertEqual(label_for(member), f'{member.user.full_name} (nick)')
        self.assertEqual(label_for(member.user), member.user.full_name)
        self.assertEqual(label_for(None), '')

    def test_system_event_without_request(self):
        team = TeamFactory()
        event = record_audit_event(AuditActionChoices.TEAM_UPDATED, target=team)
        self.assertEqual(event.actor_type, AuditActorTypeChoices.SYSTEM)
        self.assertEqual(event.organization_id, team.organization_id)
        self.assertIsNone(event.actor_user)
        self.assertIsNone(event.ip)

    def test_account_event_has_no_organization(self):
        member = MemberFactory()
        request = RequestFactory().get('/')
        request.user = member.user
        request.session = {'organization_id': member.organization_id}
        event = record_audit_event(
            AuditActionChoices.USER_PROFILE_UPDATED, request=request, target=member.user
        )
        self.assertIsNone(event.organization_id)
        self.assertEqual(event.subject_user, member.user)

    def test_session_member_of_another_organization_is_ignored(self):
        member = MemberFactory()
        team = TeamFactory()
        request = RequestFactory().get('/')
        request.user = member.user
        request.session = {'organization_id': member.organization_id}
        event = record_audit_event(
            AuditActionChoices.TEAM_UPDATED, request=request, target=team
        )
        self.assertEqual(event.organization_id, team.organization_id)
        self.assertEqual(event.actor_user, member.user)
        self.assertIsNone(event.actor_member)

    def test_errors_propagate(self):
        with patch(
            'apps.audit.models.audit_event.AuditEvent.objects.create',
            side_effect=RuntimeError('boom'),
        ):
            with self.assertRaises(RuntimeError):
                record_audit_event(
                    AuditActionChoices.TEAM_UPDATED, target=TeamFactory()
                )
