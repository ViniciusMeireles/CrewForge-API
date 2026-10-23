from django.test import TestCase
from django.utils import translation

from apps.audit.choices import (
    ACCOUNT_ACTION_PREFIXES,
    AuditActionChoices,
    AuditActorTypeChoices,
)

CATALOG = {
    'organization.created',
    'organization.updated',
    'organization.deleted',
    'organization.login',
    'organization.profile.updated',
    'organization.image.created',
    'organization.image.updated',
    'organization.image.deleted',
    'member.joined',
    'member.readmitted',
    'member.updated',
    'member.role_changed',
    'member.removed',
    'invitation.created',
    'invitation.updated',
    'invitation.email_sent',
    'invitation.deleted',
    'invitation.accepted',
    'invitation.declined',
    'team.created',
    'team.updated',
    'team.deleted',
    'team_member.added',
    'team_member.updated',
    'team_member.removed',
    'stored_file.uploaded',
    'stored_file.updated',
    'stored_file.deleted',
    'auth.signup',
    'auth.login.succeeded',
    'auth.login.failed',
    'auth.logout',
    'auth.password.changed',
    'auth.password_change.failed',
    'auth.password_reset.requested',
    'auth.password_reset.completed',
    'auth.password_reset.failed',
    'auth.email.verified',
    'auth.email_verification.failed',
    'user.profile.updated',
    'user.platform_role_changed',
}


class AuditActionChoicesTestCase(TestCase):
    def test_enum_values(self):
        self.assertEqual(set(AuditActionChoices.values), CATALOG)

    def test_stdout_only_events_are_not_audited(self):
        self.assertNotIn('auth.refresh.rejected', AuditActionChoices.values)
        self.assertNotIn('auth.throttled', AuditActionChoices.values)

    def test_values_fit_the_field(self):
        self.assertTrue(all(len(value) <= 64 for value in AuditActionChoices.values))

    def test_labels_follow_the_language(self):
        with translation.override('pt-br'):
            self.assertEqual(
                str(AuditActionChoices.MEMBER_ROLE_CHANGED.label),
                'Cargo do membro alterado',
            )

    def test_account_prefixes(self):
        self.assertEqual(ACCOUNT_ACTION_PREFIXES, ('auth.', 'user.'))


class AuditActorTypeChoicesTestCase(TestCase):
    def test_enum_values(self):
        self.assertEqual(AuditActorTypeChoices.values, ['user', 'platform', 'system'])
