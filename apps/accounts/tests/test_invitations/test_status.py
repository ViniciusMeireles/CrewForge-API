import uuid
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import InvitationStatusChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.models.invitation import Invitation
from apps.accounts.tests.mixins import APITestCaseMixin


def _past(invitation: Invitation) -> Invitation:
    Invitation.objects.filter(pk=invitation.pk).update(
        expired_at=timezone.now() - timedelta(days=1)
    )
    invitation.refresh_from_db()
    return invitation


class InvitationStatusModelTestCase(TestCase):
    def test_new_invitation_is_pending(self):
        invitation = InvitationFactory()
        self.assertEqual(invitation.status, InvitationStatusChoices.PENDING)
        self.assertFalse(invitation.is_accepted)
        self.assertFalse(invitation.is_declined)
        self.assertFalse(invitation.is_expired)

    def test_accept_sets_accepted(self):
        invitation = InvitationFactory()
        member = MemberFactory(organization=invitation.organization)
        invitation.accept(member=member, check=False)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatusChoices.ACCEPTED)
        self.assertTrue(invitation.is_accepted)

    def test_decline_sets_declined(self):
        invitation = InvitationFactory()
        invitation.decline(user=MemberFactory().user, check=False)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatusChoices.DECLINED)
        self.assertTrue(invitation.is_declined)

    def test_inactivate_sets_revoked(self):
        invitation = InvitationFactory()
        invitation.inactivate()
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatusChoices.REVOKED)

    def test_pending_past_expiry_reads_expired_without_writing(self):
        invitation = _past(InvitationFactory())
        with CaptureQueriesContext(connection) as queries:
            acceptable, _message = invitation.is_acceptable()
        self.assertFalse(acceptable)
        self.assertTrue(invitation.is_expired)
        self.assertEqual(invitation.effective_status, InvitationStatusChoices.EXPIRED)
        self.assertFalse(
            [q for q in queries.captured_queries if q['sql'].startswith('UPDATE')]
        )
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatusChoices.PENDING)

    def test_accepted_requires_accepted_at(self):
        invitation = InvitationFactory()
        with self.assertRaises(IntegrityError):
            Invitation.objects.filter(pk=invitation.pk).update(
                status=InvitationStatusChoices.ACCEPTED, accepted_at=None
            )

    def test_declined_requires_declined_at(self):
        invitation = InvitationFactory()
        with self.assertRaises(IntegrityError):
            Invitation.objects.filter(pk=invitation.pk).update(
                status=InvitationStatusChoices.DECLINED, declined_at=None
            )

    def test_expire_invites_persists_expired_status(self):
        stale = _past(InvitationFactory())
        fresh = InvitationFactory()
        call_command('expire_invites', stdout=StringIO())
        stale.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(stale.status, InvitationStatusChoices.EXPIRED)
        self.assertEqual(fresh.status, InvitationStatusChoices.PENDING)


class InvitationStatusApiTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:invitations-list')

    def test_list_exposes_effective_status(self):
        pending = InvitationFactory(organization=self.organization)
        expired = _past(InvitationFactory(organization=self.organization))
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        by_id = {item['id']: item for item in response.data['results']}
        self.assertEqual(by_id[pending.id]['status'], 'pending')
        self.assertEqual(by_id[expired.id]['status'], 'expired')
        self.assertTrue(by_id[expired.id]['is_expired'])

    def test_delete_sets_revoked(self):
        invitation = InvitationFactory(organization=self.organization)
        url = reverse('accounts:invitations-detail', args=[invitation.pk])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatusChoices.REVOKED)

    def test_status_filter(self):
        pending = InvitationFactory(organization=self.organization)
        InvitationFactory(organization=self.organization, is_declined=True)
        response = self.client.get(self.list_url, {'status': 'pending'})
        self.assertEqual(
            [item['id'] for item in response.data['results']], [pending.id]
        )

    def test_is_expired_filter_includes_pending_past_expiry(self):
        expired = _past(InvitationFactory(organization=self.organization))
        InvitationFactory(organization=self.organization)
        response = self.client.get(self.list_url, {'is_expired': 'true'})
        self.assertEqual(
            [item['id'] for item in response.data['results']], [expired.id]
        )

    def test_status_is_read_only(self):
        invitation = InvitationFactory(organization=self.organization)
        url = reverse('accounts:invitations-detail', args=[invitation.pk])
        self.client.put(
            url,
            data={
                'email': invitation.email,
                'role': invitation.role,
                'expired_at': invitation.expired_at,
                'status': 'accepted',
            },
            format='json',
        )
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatusChoices.PENDING)


class InvitationStatusMigrationTestCase(TransactionTestCase):
    before = [('accounts', '0009_email_upper_indexes')]
    after = [('accounts', '0012_invitation_status_constraints')]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        apps = executor.loader.project_state(self.before).apps
        Organization = apps.get_model('accounts', 'Organization')
        OldInvitation = apps.get_model('accounts', 'Invitation')
        slug = f'acme-{uuid.uuid4().hex[:8]}'
        organization = Organization.objects.create(name=slug, slug=slug)
        now = timezone.now()

        def make(email, **flags):
            return OldInvitation.objects.create(
                organization=organization, email=email, key=uuid.uuid4(), **flags
            ).pk

        self.ids = {
            'revoked': make('a@x.com', is_active=False, is_accepted=True),
            'accepted': make('b@x.com', is_accepted=True, accepted_at=now),
            'accepted_no_date': make('c@x.com', is_accepted=True),
            'declined': make('d@x.com', is_declined=True, is_expired=True),
            'expired': make('e@x.com', is_expired=True),
            'pending': make('f@x.com'),
        }
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.after)
        self.apps = executor.loader.project_state(self.after).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_status_by_precedence(self):
        NewInvitation = self.apps.get_model('accounts', 'Invitation')
        status = {
            name: NewInvitation.objects.get(pk=pk).status
            for name, pk in self.ids.items()
        }
        self.assertEqual(
            status,
            {
                'revoked': 'revoked',
                'accepted': 'accepted',
                'accepted_no_date': 'accepted',
                'declined': 'declined',
                'expired': 'expired',
                'pending': 'pending',
            },
        )
        self.assertIsNotNone(
            NewInvitation.objects.get(pk=self.ids['accepted_no_date']).accepted_at
        )


class InvitationUniquenessTestCase(TestCase):
    def test_key_is_unique(self):
        first = InvitationFactory()
        with self.assertRaises(IntegrityError):
            InvitationFactory(key=first.key)

    def test_single_pending_per_organization_and_email(self):
        first = InvitationFactory(email='foo@x.com')
        with self.assertRaises(IntegrityError):
            InvitationFactory(organization=first.organization, email='FOO@x.com')

    def test_pending_allowed_beside_closed_invitations(self):
        first = InvitationFactory(email='foo@x.com', is_declined=True)
        InvitationFactory(organization=first.organization, email='foo@x.com')

    def test_same_email_pending_in_other_organization(self):
        InvitationFactory(email='foo@x.com')
        InvitationFactory(email='foo@x.com')


class InvitationReinviteApiTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:invitations-list')

    def _payload(self, email):
        return {
            'email': email,
            'role': 'member',
            'expired_at': timezone.now() + timedelta(days=7),
        }

    def test_reinvite_after_unpersisted_expiry(self):
        stale = _past(
            InvitationFactory(organization=self.organization, email='foo@x.com')
        )
        response = self.client.post(
            self.list_url, data=self._payload('foo@x.com'), format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        stale.refresh_from_db()
        self.assertEqual(stale.status, InvitationStatusChoices.EXPIRED)

    def test_duplicate_constraint_maps_to_400(self):
        InvitationFactory(organization=self.organization, email='foo@x.com')
        response = self.client.post(
            self.list_url, data=self._payload('Foo@x.com'), format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)


class InvitationUniquenessMigrationTestCase(TransactionTestCase):
    before = [('accounts', '0012_invitation_status_constraints')]
    after = [('accounts', '0014_invitation_uniqueness')]

    def test_repairs_duplicates_before_constraints(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        apps = executor.loader.project_state(self.before).apps
        Organization = apps.get_model('accounts', 'Organization')
        OldInvitation = apps.get_model('accounts', 'Invitation')
        slug = f'acme-{uuid.uuid4().hex[:8]}'
        organization = Organization.objects.create(name=slug, slug=slug)
        key = uuid.uuid4()
        older = OldInvitation.objects.create(
            organization=organization, email='foo@x.com', key=key
        )
        newer = OldInvitation.objects.create(
            organization=organization, email='FOO@x.com', key=key
        )
        try:
            executor = MigrationExecutor(connection)
            executor.loader.build_graph()
            executor.migrate(self.after)
            Invitation = executor.loader.project_state(self.after).apps.get_model(
                'accounts', 'Invitation'
            )
            older = Invitation.objects.get(pk=older.pk)
            newer = Invitation.objects.get(pk=newer.pk)
            self.assertEqual(older.status, 'revoked')
            self.assertEqual(newer.status, 'pending')
            self.assertNotEqual(older.key, newer.key)
        finally:
            executor = MigrationExecutor(connection)
            executor.loader.build_graph()
            executor.migrate(executor.loader.graph.leaf_nodes())
