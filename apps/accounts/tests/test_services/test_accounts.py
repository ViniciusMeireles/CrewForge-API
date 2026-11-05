import secrets
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.organization import Organization, OrganizationProfile
from apps.accounts.models.user import User
from apps.accounts.services.auth import (
    change_password,
    confirm_password_reset,
    register_owner,
    request_password_reset,
    verify_email,
)
from apps.accounts.services.invitations import (
    InvitationRefusedError,
    lock_acceptable_invitation,
)
from apps.accounts.services.organizations import (
    create_owner_membership,
    touch_last_login,
)
from apps.accounts.services.profiles import update_profile
from apps.audit.choices import AuditActionChoices
from apps.audit.models.audit_event import AuditEvent


FIRST_SECRET = secrets.token_urlsafe(16)
NEXT_SECRET = secrets.token_urlsafe(16)


def audited(action) -> bool:
    return AuditEvent.objects.filter(action=action).exists()


class RegisterOwnerTestCase(TestCase):
    def register(self, on_user_created=lambda user: None):
        return register_owner(
            on_user_created=on_user_created,
            user_data={
                'username': 'ana',
                'email': 'ana@example.com',
                'password': FIRST_SECRET,
            },
            organization_data={
                'name': 'Acme',
                'slug': 'acme',
                'profile': {'website': 'https://acme.test'},
            },
            member_data={'nickname': 'Ana'},
        )

    def test_creates_the_user_organization_profile_and_owner(self):
        member = self.register()
        self.assertEqual(member.role, MemberRoleChoices.OWNER)
        self.assertEqual(member.nickname, 'Ana')
        self.assertEqual(member.created_by, member.user)
        self.assertTrue(member.user.check_password(FIRST_SECRET))
        self.assertEqual(member.user.created_by, member.user)
        profile = OrganizationProfile.objects.get(organization=member.organization)
        self.assertEqual(profile.website, 'https://acme.test')

    def test_rolls_back_when_the_user_callback_fails(self):
        def fail(user):
            raise RuntimeError

        with self.assertRaises(RuntimeError):
            self.register(on_user_created=fail)
        self.assertFalse(User.objects.filter(username='ana').exists())

    def test_queues_the_verification_email(self):
        member = self.register()
        self.assertIsNotNone(member.user.email_verification_sent_at)


class PasswordServiceTestCase(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_change_password_revokes_sessions_and_audits(self):
        with mock.patch('apps.accounts.services.auth.revoke_sessions') as revoke:
            change_password(user=self.user, new_password=NEXT_SECRET)
        revoke.assert_called_once_with(self.user)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEXT_SECRET))
        self.assertTrue(audited('auth.password.changed'))

    def test_change_password_rolls_back_when_the_audit_fails(self):
        with (
            mock.patch(
                'apps.accounts.services.auth.log_security_event',
                side_effect=RuntimeError,
            ),
            self.assertRaises(RuntimeError),
        ):
            change_password(user=self.user, new_password=NEXT_SECRET)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password(NEXT_SECRET))

    def test_confirm_reset_revokes_sessions_and_audits(self):
        with mock.patch('apps.accounts.services.auth.revoke_sessions') as revoke:
            confirm_password_reset(user=self.user, new_password=NEXT_SECRET)
        revoke.assert_called_once_with(self.user)
        self.assertTrue(self.user.check_password(NEXT_SECRET))
        self.assertTrue(audited('auth.password_reset.completed'))

    def test_request_reset_emails_only_a_known_user(self):
        with mock.patch('apps.accounts.tasks.send_password_reset_email') as send:
            request_password_reset(user=None)
            send.assert_not_called()
            request_password_reset(user=self.user)
        send.assert_called_once()
        self.assertTrue(audited('auth.password_reset.requested'))

    def test_verify_email_stamps_and_audits(self):
        verify_email(user=self.user)
        self.assertTrue(self.user.email_verified)
        self.assertTrue(audited('auth.email.verified'))


class UpdateProfileTestCase(TestCase):
    def setUp(self):
        self.user = UserFactory(first_name='Ana')

    def save_with(self, **fields):
        def save():
            for name, value in fields.items():
                setattr(self.user, name, value)
            self.user.save()

        return save

    def event(self):
        return AuditEvent.objects.get(action=AuditActionChoices.USER_PROFILE_UPDATED)

    def test_audits_the_changed_fields(self):
        update_profile(user=self.user, save=self.save_with(first_name='Bia'))
        fields = [change['field'] for change in self.event().changes]
        self.assertEqual(fields, ['first_name'])

    def test_no_change_records_nothing(self):
        update_profile(user=self.user, save=self.save_with(first_name='Ana'))
        self.assertFalse(audited(AuditActionChoices.USER_PROFILE_UPDATED))

    def test_email_change_hides_values_and_sends_verification(self):
        with mock.patch(
            'apps.accounts.services.profiles.send_verification_email'
        ) as send:
            update_profile(user=self.user, save=self.save_with(email='new@example.com'))
        send.assert_called_once_with(self.user)
        event = self.event()
        self.assertEqual(event.metadata, {'email_changed': True})
        self.assertEqual(
            event.changes, [{'field': 'email', 'before': None, 'after': None}]
        )


class OrganizationServiceTestCase(TestCase):
    def test_create_owner_membership(self):
        organization = Organization.objects.create(name='Bare', slug='bare')
        user = UserFactory()
        member = create_owner_membership(organization=organization, user=user)
        self.assertEqual(member.role, MemberRoleChoices.OWNER)
        self.assertEqual(member.created_by, user)

    def test_touch_last_login(self):
        member = MemberFactory()
        before = timezone.now()
        touch_last_login(member=member)
        member.refresh_from_db()
        self.assertGreaterEqual(member.last_login_at, before)


class LockAcceptableInvitationTestCase(TestCase):
    def test_yields_the_pending_invitation(self):
        invitation = InvitationFactory()
        pending = Invitation.objects.filter(pk=invitation.pk)
        with lock_acceptable_invitation(pending=pending) as locked:
            self.assertEqual(locked, invitation)

    def test_yields_none_without_a_match(self):
        with lock_acceptable_invitation(pending=Invitation.objects.none()) as locked:
            self.assertIsNone(locked)

    def test_refuses_an_answered_invitation(self):
        invitation = InvitationFactory()
        invitation.decline(user=UserFactory())
        pending = Invitation.objects.filter(pk=invitation.pk)
        with (
            self.assertRaises(InvitationRefusedError),
            lock_acceptable_invitation(pending=pending),
        ):
            self.fail('The body must not run')
