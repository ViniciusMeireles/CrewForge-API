import uuid
from datetime import timedelta

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.choices import InvitationErrorMessages, MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.models.invitation import Invitation


class InvitationModelTestCase(TestCase):
    def test_str(self):
        invitation = InvitationFactory()
        self.assertEqual(str(invitation), invitation.email)

    def test_key_auto_generated_on_save(self):
        invitation = InvitationFactory.create(key=None)
        self.assertIsNotNone(invitation.key)
        self.assertIsInstance(invitation.key, uuid.UUID)

    def test_key_preserved_when_provided(self):
        key = uuid.uuid4()
        invitation = InvitationFactory(key=key)
        self.assertEqual(invitation.key, key)

    def test_is_acceptable_returns_true(self):
        invitation = InvitationFactory(
            is_accepted=False,
            is_expired=False,
            expired_at=timezone.now() + timedelta(days=7),
        )
        is_acceptable, message = invitation.is_acceptable()
        self.assertTrue(is_acceptable)
        self.assertEqual(message, '')

    def test_is_acceptable_expired_returns_false(self):
        invitation = InvitationFactory(
            is_expired=True,
            expired_at=timezone.now() - timedelta(days=1),
        )
        is_acceptable, message = invitation.is_acceptable()
        self.assertFalse(is_acceptable)
        self.assertEqual(message, str(InvitationErrorMessages.INVITATION_EXPIRED.label))

    def test_is_acceptable_past_expired_at_sets_is_expired(self):
        invitation = InvitationFactory(
            is_expired=False,
            expired_at=timezone.now() - timedelta(days=1),
        )
        is_acceptable, message = invitation.is_acceptable()
        self.assertFalse(is_acceptable)
        self.assertTrue(invitation.is_expired)
        self.assertEqual(message, str(InvitationErrorMessages.INVITATION_EXPIRED.label))

    def test_is_acceptable_accepted_returns_false(self):
        invitation = InvitationFactory(
            is_accepted=True,
            is_expired=False,
            expired_at=timezone.now() + timedelta(days=7),
        )
        is_acceptable, message = invitation.is_acceptable()
        self.assertFalse(is_acceptable)
        self.assertEqual(
            message, str(InvitationErrorMessages.INVITATION_ACCEPTED.label)
        )

    def test_is_acceptable_user_already_member_returns_false(self):
        member = MemberFactory()
        invitation = InvitationFactory(
            organization=member.organization,
            email=member.user.email,
            is_accepted=False,
            is_expired=False,
            expired_at=timezone.now() + timedelta(days=7),
        )
        is_acceptable, message = invitation.is_acceptable()
        self.assertFalse(is_acceptable)
        self.assertEqual(
            message, str(InvitationErrorMessages.USER_ALREADY_MEMBER.label)
        )

    def test_get_invitation_link(self):
        invitation = InvitationFactory()
        expected = f'{settings.FRONTEND_URL}/invitations/{invitation.key}/accept'
        self.assertEqual(invitation.get_invitation_link(), expected)

    @override_settings(FRONTEND_URL=None)
    def test_get_invitation_link_without_frontend_url(self):
        invitation = InvitationFactory()
        expected = f'None/invitations/{invitation.key}/accept'
        self.assertEqual(invitation.get_invitation_link(), expected)

    def test_accept_sets_member_and_accepted(self):
        invitation = InvitationFactory(
            is_accepted=False,
            is_expired=False,
            expired_at=timezone.now() + timedelta(days=7),
        )
        member = MemberFactory(organization=invitation.organization)
        invitation.accept(member=member)
        self.assertTrue(invitation.is_accepted)
        self.assertEqual(invitation.member, member)

    def test_accept_raises_on_expired(self):
        invitation = InvitationFactory(
            is_expired=True,
            expired_at=timezone.now() - timedelta(days=1),
        )
        member = MemberFactory(organization=invitation.organization)
        with self.assertRaises(ValueError):
            invitation.accept(member=member)

    def test_accept_with_check_false_skips_validation(self):
        invitation = InvitationFactory(
            is_expired=True,
            expired_at=timezone.now() - timedelta(days=1),
        )
        member = MemberFactory(organization=invitation.organization)
        invitation.accept(member=member, check=False)
        self.assertTrue(invitation.is_accepted)
        self.assertEqual(invitation.member, member)

    def test_clean_raises_on_past_expired_at(self):
        invitation = InvitationFactory.build(
            expired_at=timezone.now() - timedelta(days=1),
        )
        with self.assertRaises(ValueError):
            invitation.clean()

    def test_clean_passes_on_future_expired_at(self):
        invitation = InvitationFactory.build(
            expired_at=timezone.now() + timedelta(days=7),
        )
        invitation.clean()

    def test_get_user_returns_none_when_no_user(self):
        invitation = InvitationFactory(email='nonexistent@example.com')
        self.assertIsNone(invitation.get_user())

    def test_send_email_dispatches_task(self):
        invitation = InvitationFactory(
            is_accepted=False,
            is_expired=False,
            expired_at=timezone.now() + timedelta(days=7),
        )
        with (
            override_settings(FRONTEND_URL='http://example.com'),
            self.assertLogs('celery', level='DEBUG') as logs,
        ):
            invitation.send_email()
        self.assertTrue(
            any('Task apps.generics.tasks.send_email' in line for line in logs.output),
        )

    def test_filter_actives_excludes_inactive(self):
        InvitationFactory(is_active=False)
        active = InvitationFactory()
        qs = Invitation.objects.filter_actives()
        self.assertIn(active, qs)
        self.assertEqual(qs.count(), 1)

    def test_filter_inactives(self):
        inactive = InvitationFactory(is_active=False)
        InvitationFactory()
        qs = Invitation.objects.filter_inactives()
        self.assertIn(inactive, qs)

    def test_get_or_none_found(self):
        invitation = InvitationFactory()
        result = Invitation.objects.get_or_none(id=invitation.id)
        self.assertEqual(result, invitation)

    def test_get_or_none_not_found(self):
        result = Invitation.objects.get_or_none(id=99999)
        self.assertIsNone(result)

    def test_default_role_is_member(self):
        invitation = InvitationFactory()
        self.assertEqual(invitation.role, MemberRoleChoices.MEMBER)

    def test_default_is_accepted_is_false(self):
        invitation = InvitationFactory()
        self.assertFalse(invitation.is_accepted)

    def test_ordering(self):
        inv1 = InvitationFactory()
        inv2 = InvitationFactory()
        qs = Invitation.objects.all()
        self.assertEqual(qs[0], inv2)
        self.assertEqual(qs[1], inv1)
