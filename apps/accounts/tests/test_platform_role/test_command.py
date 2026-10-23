from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.factories.users import UserFactory
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.models.audit_event import AuditEvent


class SetPlatformRoleCommandTestCase(TestCase):
    def call(self, *args):
        out = StringIO()
        call_command('set_platform_role', *args, stdout=out)
        return out.getvalue()

    def test_grants_the_role_and_records_an_account_event(self):
        user = UserFactory()
        self.call(user.email, 'admin')
        user.refresh_from_db()
        self.assertEqual(user.platform_role, 'admin')
        event = AuditEvent.objects.get(
            action=AuditActionChoices.USER_PLATFORM_ROLE_CHANGED
        )
        self.assertIsNone(event.organization_id)
        self.assertEqual(event.subject_user_id, user.id)
        self.assertEqual(event.actor_type, AuditActorTypeChoices.SYSTEM)
        self.assertEqual(
            event.changes,
            [{'field': 'platform_role', 'before': 'none', 'after': 'admin'}],
        )

    def test_same_role_records_nothing(self):
        user = UserFactory(platform_role='support')
        self.assertIn('already', self.call(user.username, 'support'))
        self.assertFalse(AuditEvent.objects.exists())

    def test_unknown_user(self):
        with self.assertRaises(CommandError):
            self.call('nobody@example.com', 'admin')

    def test_invalid_role(self):
        user = UserFactory()
        with self.assertRaises(CommandError):
            self.call(user.username, 'owner')
