from django.test import TestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.audit.choices import AuditActionChoices
from apps.audit.models.audit_event import AuditEvent
from apps.audit.serializers.audit_event import AuditEventSerializer
from apps.audit.services import record_audit_event


class AuditDurabilityTestCase(TestCase):
    def test_event_survives_organization_hard_delete(self):
        organization = OrganizationFactory(name='Gone Corp')
        event = record_audit_event(
            AuditActionChoices.ORGANIZATION_UPDATED,
            organization_id=organization.pk,
            target=organization,
        )
        organization.members.all().delete()
        organization.delete()
        event = AuditEvent.objects.get(pk=event.pk)
        self.assertIsNone(event.organization_id)
        self.assertEqual(event.organization_name, 'Gone Corp')

    def test_event_survives_subject_user_hard_delete(self):
        user = UserFactory(
            email='gone@example.com', first_name='Gone', last_name='User'
        )
        event = record_audit_event(
            AuditActionChoices.AUTH_PASSWORD_CHANGED,
            subject_user_id=user.pk,
            actor_user=user,
        )
        user.delete()
        event = AuditEvent.objects.get(pk=event.pk)
        self.assertIsNone(event.subject_user_id)
        self.assertIn('gone@example.com', event.subject_label)
        self.assertIn('Gone User', event.subject_label)

    def test_bulk_update_is_refused(self):
        record_audit_event(AuditActionChoices.ORGANIZATION_UPDATED)
        with self.assertRaises(RuntimeError):
            AuditEvent.objects.all().update(target_label='tampered')

    def test_bulk_delete_is_refused(self):
        record_audit_event(AuditActionChoices.ORGANIZATION_UPDATED)
        with self.assertRaises(RuntimeError):
            AuditEvent.objects.all().delete()
        self.assertEqual(AuditEvent._base_manager.count(), 1)

    def test_serializer_exposes_snapshots(self):
        organization = OrganizationFactory(name='Snap Corp')
        event = record_audit_event(
            AuditActionChoices.ORGANIZATION_UPDATED,
            organization_id=organization.pk,
            target=organization,
        )
        data = AuditEventSerializer(event).data
        self.assertEqual(data['organization_name'], 'Snap Corp')
        self.assertIn('subject_label', data)
