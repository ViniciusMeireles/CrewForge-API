from types import SimpleNamespace
from unittest import mock

from django.db import transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.billing.entitlements import BYTES_PER_MB, has_feature
from apps.billing.exceptions import (
    PlanLimitReached,
    PlanLimitReachedError,
    format_storage,
)
from apps.billing.models.subscription import Subscription
from apps.billing.services import ensure_within_limit
from apps.teams.factories.teams import TeamFactory


class EnsureWithinLimitTestCase(TestCase):
    def test_needs_an_open_transaction(self):
        organization = OrganizationFactory()
        outside = SimpleNamespace(in_atomic_block=False)
        with (
            mock.patch.object(transaction, 'get_connection', return_value=outside),
            self.assertRaises(RuntimeError),
        ):
            ensure_within_limit(organization=organization, key='max_teams')

    def test_unknown_key(self):
        organization = OrganizationFactory()
        with self.assertRaises(ValueError):
            ensure_within_limit(organization=organization, key='max_projects')

    def test_nothing_added_is_always_allowed(self):
        organization = OrganizationFactory(subscription=False)
        ensure_within_limit(organization=organization, key='storage_bytes', adding=0)

    def test_missing_subscription_fails_closed_to_free(self):
        organization = OrganizationFactory(subscription=False)
        TeamFactory(organization=organization)
        with (
            self.assertLogs('apps.billing.services', level='ERROR'),
            self.assertRaises(PlanLimitReached) as ctx,
        ):
            ensure_within_limit(organization=organization, key='max_teams')
        self.assertEqual((ctx.exception.current, ctx.exception.maximum), (1, 1))

    def test_missing_subscription_has_no_features(self):
        organization = OrganizationFactory(subscription=False)
        with self.assertLogs('apps.billing.entitlements', level='ERROR'):
            self.assertFalse(has_feature(organization.owner, 'audit'))

    def test_missing_subscription_logs_once_per_organization(self):
        organization = OrganizationFactory(subscription=False)
        member = organization.owner
        with self.assertLogs('apps.billing.entitlements', level='ERROR') as logs:
            has_feature(member, 'audit')
            has_feature(member, 'audit')
        self.assertEqual(len(logs.records), 1)

    def test_limit_messages_use_the_singular_for_one(self):
        cases = {
            ('max_members', 1): 'Your plan allows up to 1 member.',
            ('max_members', 3): 'Your plan allows up to 3 members.',
            ('max_teams', 1): 'Your plan allows up to 1 team.',
            ('max_teams', 5): 'Your plan allows up to 5 teams.',
        }
        for (key, maximum), message in cases.items():
            with self.subTest(key=key, maximum=maximum):
                error = PlanLimitReachedError.from_limit(
                    PlanLimitReached(key, maximum, maximum)
                )
                self.assertEqual(str(error.detail), message)
        with translation.override('pt-br'):
            error = PlanLimitReachedError.from_limit(
                PlanLimitReached('max_teams', 1, 1)
            )
            self.assertEqual(str(error.detail), 'Seu plano permite até 1 equipe.')

    def test_format_storage(self):
        self.assertEqual(format_storage(5120 * BYTES_PER_MB), '5 GB')
        self.assertEqual(format_storage(100 * BYTES_PER_MB), '100 MB')
        self.assertEqual(format_storage(1536 * BYTES_PER_MB), '1536 MB')


class SubscriptionMissingViewTestCase(APITestCaseMixin, APITestCase):
    def test_missing_subscription_is_a_conflict(self):
        organization = self.new_account()
        Subscription.objects.filter(organization=organization).delete()
        response = self.client.get(reverse('billing:subscription'))
        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
