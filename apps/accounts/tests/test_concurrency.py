import threading
from unittest import mock

from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.choices import InvitationStatusChoices, MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import DEFAULT_PASSWORD, UserFactory
from apps.accounts.models.member import Member
from apps.accounts.models.user import User
from apps.accounts.serializers.invitation import InvitationSerializer


def run_concurrently(*calls):
    """Run each callable in its own thread, released together by a barrier."""
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def worker(index, call):
        try:
            barrier.wait()
            results[index] = call()
        except Exception as exc:
            results[index] = exc
        finally:
            connection.close()

    threads = [
        threading.Thread(target=worker, args=(i, call)) for i, call in enumerate(calls)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


class InvitationConcurrencyTestCase(TransactionTestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.user = UserFactory()
        self.invitation = InvitationFactory(
            organization=self.organization, email=self.user.email
        )

    def _post(self, action):
        url = reverse(
            f'accounts:invitations-{action}',
            kwargs={'invitation_pk': self.invitation.pk},
        )
        return lambda: _client(self.user).post(url, format='json').status_code

    def test_concurrent_accept_creates_one_member(self):
        codes = run_concurrently(self._post('accept'), self._post('accept'))
        self.assertEqual(sorted(codes), [200, 400])
        self.assertEqual(
            Member.objects.filter(
                user=self.user, organization=self.organization
            ).count(),
            1,
        )

    def test_concurrent_accept_and_decline_keep_one_outcome(self):
        codes = run_concurrently(self._post('accept'), self._post('decline'))
        self.assertEqual(sorted(codes), [200, 400])
        self.invitation.refresh_from_db()
        self.assertIn(
            self.invitation.status,
            {InvitationStatusChoices.ACCEPTED, InvitationStatusChoices.DECLINED},
        )
        member_exists = Member.objects.filter(
            user=self.user, organization=self.organization
        ).exists()
        self.assertEqual(
            member_exists,
            self.invitation.status == InvitationStatusChoices.ACCEPTED,
        )


class SignupByKeyConcurrencyTestCase(TransactionTestCase):
    def test_concurrent_signup_creates_one_user(self):
        invitation = InvitationFactory(email='new.person@example.com')
        url = reverse('accounts:members-create-with-invite', args=[invitation.key])

        def signup(username):
            payload = {
                'user': {
                    'username': username,
                    'first_name': 'New',
                    'last_name': 'Person',
                    'password': DEFAULT_PASSWORD,
                },
                'nickname': username,
            }
            return lambda: _client().post(url, data=payload, format='json').status_code

        codes = run_concurrently(signup('first'), signup('second'))
        self.assertEqual(codes.count(201), 1)
        self.assertTrue(all(code in (201, 400, 404) for code in codes))
        self.assertEqual(
            User.objects.filter(email__iexact='new.person@example.com').count(), 1
        )


class AdmitConcurrencyTestCase(TransactionTestCase):
    def test_concurrent_admit_keeps_one_membership(self):
        organization = OrganizationFactory()
        user = UserFactory()

        def admit():
            return Member.objects.admit(
                user=user, organization=organization, role=MemberRoleChoices.MEMBER
            )

        results = run_concurrently(admit, admit)
        errors = [r for r in results if isinstance(r, Exception)]
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValueError)
        self.assertEqual(
            Member.objects.filter(user=user, organization=organization).count(), 1
        )


class InviteConcurrencyTestCase(TransactionTestCase):
    def test_concurrent_invites_of_one_email(self):
        organization = OrganizationFactory()
        owner = organization.owner
        url = reverse('accounts:invitations-list')

        def invite():
            client = APIClient()
            client.force_authenticate(user=owner.user)
            client.post(reverse('accounts:organizations-login', args=[organization.pk]))
            payload = {'email': 'dup@example.com', 'role': MemberRoleChoices.MEMBER}
            return client.post(url, data=payload, format='json').status_code

        codes = run_concurrently(invite, invite)
        self.assertEqual(sorted(codes), [201, 400])


class TransferConcurrencyTestCase(TransactionTestCase):
    def test_concurrent_transfers_keep_one_owner(self):
        from apps.platform.services import transfer_ownership

        organization = OrganizationFactory()
        first = MemberFactory(organization=organization, role=MemberRoleChoices.ADMIN)
        second = MemberFactory(organization=organization, role=MemberRoleChoices.ADMIN)
        request = mock.Mock(user=UserFactory(), impersonator=None)

        def transfer(member):
            return lambda: transfer_ownership(
                request, organization, member, reason='Support request'
            )

        run_concurrently(transfer(first), transfer(second))
        self.assertEqual(
            Member.objects.filter(
                organization=organization, role=MemberRoleChoices.OWNER, is_active=True
            ).count(),
            1,
        )


def _owner_request(organization):
    django_request = APIRequestFactory().post('/')
    django_request.session = {'organization_id': organization.pk}
    request = Request(django_request)
    request.user = organization.owner.user
    return request


class InvitationEmailAfterCommitTestCase(TestCase):
    def test_email_is_not_queued_when_the_transaction_rolls_back(self):
        organization = OrganizationFactory()
        request = _owner_request(organization)
        with mock.patch('apps.accounts.tasks.send_invitation_email') as send:
            with self.captureOnCommitCallbacks(execute=True):
                try:
                    with transaction.atomic():
                        serializer = InvitationSerializer(
                            data={
                                'email': 'later@example.com',
                                'role': MemberRoleChoices.MEMBER,
                                'send_email': True,
                            },
                            context={'request': request},
                        )
                        serializer.is_valid(raise_exception=True)
                        serializer.save(organization=organization)
                        raise RuntimeError('rollback')
                except RuntimeError:
                    pass
        send.assert_not_called()

    def test_email_is_queued_after_commit(self):
        organization = OrganizationFactory()
        request = _owner_request(organization)
        with mock.patch('apps.accounts.tasks.send_invitation_email') as send:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                serializer = InvitationSerializer(
                    data={
                        'email': 'later@example.com',
                        'role': MemberRoleChoices.MEMBER,
                        'send_email': True,
                    },
                    context={'request': request},
                )
                serializer.is_valid(raise_exception=True)
                serializer.save(organization=organization)
                send.assert_not_called()
            for callback in callbacks:
                callback()
        send.assert_called_once()
