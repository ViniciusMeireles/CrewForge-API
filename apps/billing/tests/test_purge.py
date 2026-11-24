from datetime import timedelta

from django.db.models import QuerySet
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.audit.choices import AuditActionChoices
from apps.audit.models.audit_event import AuditEvent
from apps.audit.services import record_audit_event
from apps.billing.tasks import purge_audit_events
from apps.billing.tests.helpers import set_plan


def event(organization=None, days_ago=0, user=None):
    created = record_audit_event(
        AuditActionChoices.TEAM_CREATED
        if organization
        else AuditActionChoices.AUTH_LOGOUT,
        organization_id=organization.pk if organization else None,
        target_type='team',
        target_id=1,
        target_label='Team',
        subject_user_id=user.pk if user else None,
    )
    QuerySet(AuditEvent).filter(pk=created.pk).update(
        created_at=timezone.now() - timedelta(days=days_ago)
    )
    return created


class PurgeTestCase(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        set_plan(self.organization, audit_retention_days=90)

    def test_purges_old_organization_events(self):
        old = event(self.organization, days_ago=91)
        recent = event(self.organization, days_ago=89)
        self.assertEqual(purge_audit_events.apply().get(), 1)
        self.assertFalse(AuditEvent.objects.filter(pk=old.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(pk=recent.pk).exists())

    def test_keeps_account_events(self):
        account = event(days_ago=400, user=UserFactory())
        purge_audit_events.apply()
        self.assertTrue(AuditEvent.objects.filter(pk=account.pk).exists())

    def test_null_retention_keeps_all(self):
        set_plan(self.organization, audit_retention_days=None)
        old = event(self.organization, days_ago=4000)
        purge_audit_events.apply()
        self.assertTrue(AuditEvent.objects.filter(pk=old.pk).exists())

    def test_other_organizations_follow_their_plan(self):
        other = OrganizationFactory()
        set_plan(other, audit_retention_days=365)
        kept = event(other, days_ago=200)
        purge_audit_events.apply()
        self.assertTrue(AuditEvent.objects.filter(pk=kept.pk).exists())

    @override_settings(AUDIT_RETENTION_PURGE_ENABLED=False)
    def test_disabled_setting(self):
        old = event(self.organization, days_ago=91)
        self.assertEqual(purge_audit_events.apply().get(), 0)
        self.assertTrue(AuditEvent.objects.filter(pk=old.pk).exists())

    def test_events_stay_immutable(self):
        with self.assertRaises(RuntimeError):
            AuditEvent.objects.all().delete()
        with self.assertRaises(RuntimeError):
            AuditEvent.objects.all().update(action='x')
