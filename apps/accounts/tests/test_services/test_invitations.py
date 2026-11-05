from datetime import timedelta
from unittest import mock

from django.http import Http404
from django.test import TestCase
from django.utils import timezone

from apps.accounts.choices import InvitationStatusChoices, MemberRoleChoices
from apps.accounts.consts import INVITATION_EMAIL_COOLDOWN_SECONDS
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.models.member import Member
from apps.accounts.selectors.invitations import invitations_by_key, received_invitations
from apps.accounts.services.invitations import (
    InvitationEmailCooldownError,
    InvitationRefusedError,
    accept_invitation,
    decline_invitation,
    expire_stale_invitations,
    resend_invitation_email,
    send_invitation_on_commit,
)
from apps.audit.choices import AuditActionChoices
from apps.audit.models.audit_event import AuditEvent


class InvitationServiceTestCase(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.user = UserFactory()
        self.invitation = InvitationFactory(
            organization=self.organization,
            email=self.user.email,
            role=MemberRoleChoices.MANAGER,
        )

    def audited(self, action) -> bool:
        return AuditEvent.objects.filter(action=action).exists()

    def test_accept_creates_the_member_and_audits_without_a_request(self):
        accepted = accept_invitation(
            invitation_pk=self.invitation.pk, user=self.user, nickname='Ana'
        )
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, InvitationStatusChoices.ACCEPTED)
        self.assertEqual(accepted.member.role, MemberRoleChoices.MANAGER)
        self.assertEqual(accepted.member.nickname, 'Ana')
        self.assertFalse(accepted.readmitted)
        self.assertTrue(self.audited(AuditActionChoices.INVITATION_ACCEPTED))
        self.assertTrue(self.audited(AuditActionChoices.MEMBER_JOINED))

    def test_accept_readmits_a_former_member(self):
        former = Member.objects.create(
            user=self.user, organization=self.organization, is_active=False
        )
        accepted = accept_invitation(invitation_pk=self.invitation.pk, user=self.user)
        self.assertEqual(accepted.member.pk, former.pk)
        self.assertTrue(accepted.readmitted)
        self.assertTrue(self.audited(AuditActionChoices.MEMBER_READMITTED))

    def test_accept_rolls_back_when_the_check_refuses(self):
        def refuse(invitation):
            raise PermissionError

        with self.assertRaises(PermissionError):
            accept_invitation(
                invitation_pk=self.invitation.pk, user=self.user, check=refuse
            )
        self.assertFalse(Member.objects.filter(user=self.user).exists())

    def test_accept_refuses_an_answered_invitation(self):
        accept_invitation(invitation_pk=self.invitation.pk, user=self.user)
        with self.assertRaises(InvitationRefusedError):
            accept_invitation(invitation_pk=self.invitation.pk, user=self.user)

    def test_unknown_invitation_is_not_found(self):
        with self.assertRaises(Http404):
            accept_invitation(invitation_pk='0', user=self.user)

    def test_decline_updates_and_audits(self):
        decline_invitation(invitation_pk=self.invitation.pk, user=self.user)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, InvitationStatusChoices.DECLINED)
        self.assertTrue(self.audited(AuditActionChoices.INVITATION_DECLINED))

    def test_decline_refuses_an_answered_invitation(self):
        decline_invitation(invitation_pk=self.invitation.pk, user=self.user)
        with self.assertRaises(InvitationRefusedError):
            decline_invitation(invitation_pk=self.invitation.pk, user=self.user)

    def test_resend_stamps_audits_and_sends_after_commit(self):
        with (
            mock.patch.object(type(self.invitation), 'send_email') as send,
            self.captureOnCommitCallbacks(execute=True),
        ):
            resend_invitation_email(invitation=self.invitation)
        send.assert_called_once_with()
        self.assertIsNotNone(self.invitation.last_email_sent_at)
        self.assertTrue(self.audited(AuditActionChoices.INVITATION_EMAIL_SENT))

    def test_resend_reports_the_remaining_cooldown(self):
        self.invitation.last_email_sent_at = timezone.now() - timedelta(seconds=1)
        with self.assertRaises(InvitationEmailCooldownError) as raised:
            resend_invitation_email(invitation=self.invitation)
        self.assertLess(raised.exception.retry_after, INVITATION_EMAIL_COOLDOWN_SECONDS)

    def test_resend_refuses_an_answered_invitation(self):
        decline_invitation(invitation_pk=self.invitation.pk, user=self.user)
        self.invitation.refresh_from_db()
        with self.assertRaises(InvitationRefusedError):
            resend_invitation_email(invitation=self.invitation)

    def test_expire_stale_invitations_only_touches_lapsed_ones(self):
        lapsed = InvitationFactory(organization=self.organization, email='a@b.co')
        type(lapsed).objects.filter(pk=lapsed.pk).update(
            expired_at=timezone.now() - timedelta(days=1)
        )
        expire_stale_invitations(organization=self.organization, email='A@B.co')
        lapsed.refresh_from_db()
        self.invitation.refresh_from_db()
        self.assertEqual(lapsed.status, InvitationStatusChoices.EXPIRED)
        self.assertEqual(self.invitation.status, InvitationStatusChoices.PENDING)

    def test_send_on_commit_skips_an_answered_invitation(self):
        decline_invitation(invitation_pk=self.invitation.pk, user=self.user)
        self.invitation.refresh_from_db()
        with (
            mock.patch.object(type(self.invitation), 'send_email') as send,
            self.captureOnCommitCallbacks(execute=True),
        ):
            send_invitation_on_commit(self.invitation)
        send.assert_not_called()


class InvitationSelectorTestCase(TestCase):
    def test_by_key_falls_back_to_pending_without_a_verified_user(self):
        invitation = InvitationFactory()
        self.assertIn(invitation, invitations_by_key(user=None))

    def test_by_key_uses_the_received_list_for_a_verified_user(self):
        user = UserFactory(email_verified_at=timezone.now())
        mine = InvitationFactory(email=user.email)
        other = InvitationFactory()
        keyed = invitations_by_key(user=user)
        self.assertIn(mine, keyed)
        self.assertNotIn(other, keyed)
        self.assertIn(mine, received_invitations(user=user))
