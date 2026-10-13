from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.models.invitation import Invitation


class InvitationQuerySetAcceptableBoundaryTestCase(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.now = timezone.now()

    def test_expired_at_equal_to_now_is_not_acceptable(self):
        InvitationFactory(organization=self.organization, expired_at=self.now)
        self.assertFalse(Invitation.objects.filter_acceptable().exists())

    def test_expired_at_after_now_is_acceptable(self):
        InvitationFactory(
            organization=self.organization,
            expired_at=self.now + timedelta(seconds=1),
        )
        self.assertTrue(Invitation.objects.filter_acceptable().exists())

    def test_expired_at_in_the_past_is_not_acceptable(self):
        InvitationFactory(
            organization=self.organization,
            expired_at=self.now - timedelta(seconds=1),
        )
        self.assertFalse(Invitation.objects.filter_acceptable().exists())
