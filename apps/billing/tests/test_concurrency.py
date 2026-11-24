from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connection, transaction
from django.test import TransactionTestCase, skipUnlessDBFeature

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.models.invitation import Invitation
from apps.accounts.models.organization import Organization
from apps.accounts.services.organizations import create_owner_membership
from apps.billing.choices import SubscriptionStatusChoices
from apps.billing.exceptions import PlanLimitReached
from apps.billing.models.subscription import Subscription
from apps.billing.services import ensure_within_limit, start_subscription
from apps.billing.tests.helpers import set_plan


@skipUnlessDBFeature('has_select_for_update')
class LimitConcurrencyTestCase(TransactionTestCase):
    def run_parallel(self, work, count=2):
        barrier = Barrier(count)

        def task(index):
            close_old_connections()
            try:
                barrier.wait()
                return work(index)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=count) as pool:
            return list(pool.map(task, range(count)))

    def test_parallel_invitations_at_the_limit(self):
        organization = OrganizationFactory()
        set_plan(organization, max_members=2)

        def invite(index):
            try:
                with transaction.atomic():
                    ensure_within_limit(
                        organization=organization, key='max_members', count_pending=True
                    )
                    Invitation.objects.create(
                        organization=organization,
                        email=f'parallel{index}@example.com',
                        role=MemberRoleChoices.MEMBER,
                    )
                return 'created'
            except PlanLimitReached:
                return 'refused'

        self.assertEqual(sorted(self.run_parallel(invite)), ['created', 'refused'])

    def test_parallel_creations_one_trial(self):
        owner = UserFactory()

        def create(index):
            with transaction.atomic():
                organization = Organization.objects.create(
                    name=f'Parallel {index}', slug=f'parallel-{index}'
                )
                create_owner_membership(organization=organization, user=owner)
                return start_subscription(organization=organization, owner=owner).status

        self.assertEqual(
            sorted(self.run_parallel(create)),
            [SubscriptionStatusChoices.ACTIVE, SubscriptionStatusChoices.TRIALING],
        )
        self.assertEqual(Subscription.objects.count(), 2)
