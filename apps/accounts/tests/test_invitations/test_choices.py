from django.test import TestCase

from apps.accounts.choices import (
    InvitationEmailErrorMessages,
    InvitationErrorMessages,
)


class InvitationErrorMessagesTestCase(TestCase):
    def test_values_count(self):
        self.assertEqual(len(InvitationErrorMessages), 4)

    def test_invitation_expired(self):
        self.assertEqual(
            InvitationErrorMessages.INVITATION_EXPIRED.value,
            'invitation_expired',
        )
        self.assertEqual(
            InvitationErrorMessages.INVITATION_EXPIRED.label,
            'Invitation is expired',
        )

    def test_invitation_not_found(self):
        self.assertEqual(
            InvitationErrorMessages.INVITATION_NOT_FOUND.value,
            'invitation_not_found',
        )
        self.assertEqual(
            InvitationErrorMessages.INVITATION_NOT_FOUND.label,
            'Invitation not found or expired',
        )

    def test_invitation_accepted(self):
        self.assertEqual(
            InvitationErrorMessages.INVITATION_ACCEPTED.value,
            'invitation_accepted',
        )
        self.assertEqual(
            InvitationErrorMessages.INVITATION_ACCEPTED.label,
            'Invitation already accepted',
        )

    def test_user_already_member(self):
        self.assertEqual(
            InvitationErrorMessages.USER_ALREADY_MEMBER.value,
            'user_already_member',
        )
        self.assertEqual(
            InvitationErrorMessages.USER_ALREADY_MEMBER.label,
            'User is already a member',
        )


class InvitationEmailErrorMessagesTestCase(TestCase):
    def test_values_count(self):
        self.assertEqual(len(InvitationEmailErrorMessages), 3)

    def test_cooldown_active(self):
        self.assertEqual(
            InvitationEmailErrorMessages.COOLDOWN_ACTIVE.value,
            'cooldown_active',
        )
        self.assertEqual(
            InvitationEmailErrorMessages.COOLDOWN_ACTIVE.label,
            'An invitation email was recently sent. Please wait before resending.',
        )

    def test_sent_success(self):
        self.assertEqual(
            InvitationEmailErrorMessages.SENT_SUCCESS.value,
            'sent_success',
        )
        self.assertEqual(
            InvitationEmailErrorMessages.SENT_SUCCESS.label,
            'Invitation email sent successfully.',
        )

    def test_invitation_not_acceptable(self):
        self.assertEqual(
            InvitationEmailErrorMessages.INVITATION_NOT_ACCEPTABLE.value,
            'invitation_not_acceptable',
        )
        self.assertEqual(
            InvitationEmailErrorMessages.INVITATION_NOT_ACCEPTABLE.label,
            'The invitation is no longer valid.',
        )
