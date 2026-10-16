from django.test import TestCase

from apps.accounts.factories.users import UserFactory
from apps.audit.choices import AuditActionChoices
from apps.audit.factories.audit_event import AuditEventFactory
from apps.audit.models.audit_event import AuditEvent


class AuditEventModelTestCase(TestCase):
    def test_str(self):
        event = AuditEventFactory(target_label='Design')
        self.assertEqual(str(event), 'team.created - Design')

    def test_update_is_refused(self):
        event = AuditEventFactory()
        event.target_label = 'changed'
        with self.assertRaises(RuntimeError):
            event.save()

    def test_delete_is_refused(self):
        event = AuditEventFactory()
        with self.assertRaises(RuntimeError):
            event.delete()
        self.assertTrue(AuditEvent.objects.filter(pk=event.pk).exists())

    def test_default_values(self):
        event = AuditEventFactory()
        self.assertEqual(event.changes, [])
        self.assertEqual(event.metadata, {})
        self.assertIsNone(event.impersonator)

    def test_ordering_newest_first(self):
        first = AuditEventFactory()
        second = AuditEventFactory()
        self.assertEqual(list(AuditEvent.objects.all()[:2]), [second, first])

    def test_for_organization(self):
        event = AuditEventFactory()
        AuditEventFactory()
        self.assertEqual(
            list(AuditEvent.objects.for_organization(event.organization_id)), [event]
        )

    def test_account_activity(self):
        own = AuditEventFactory(account=True)
        user = own.subject_user
        AuditEventFactory(account=True)
        AuditEventFactory(actor_member__user=user)
        AuditEventFactory(
            account=True,
            subject_user=user,
            actor_user=user,
            action=AuditActionChoices.TEAM_CREATED,
        )
        failed = AuditEventFactory(
            account=True,
            actor_user=None,
            actor_label='',
            subject_user=user,
            action=AuditActionChoices.AUTH_LOGIN_FAILED,
        )
        self.assertEqual(list(AuditEvent.objects.account_activity(user)), [failed, own])

    def test_account_activity_of_another_user_is_empty(self):
        AuditEventFactory(account=True)
        self.assertFalse(AuditEvent.objects.account_activity(UserFactory()).exists())
