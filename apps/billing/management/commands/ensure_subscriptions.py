from django.core.management.base import BaseCommand

from apps.accounts.models.organization import Organization
from apps.billing.backfill import create_courtesy_subscriptions
from apps.billing.models.plan import Plan
from apps.billing.models.subscription import Subscription


class Command(BaseCommand):
    help = 'Give every organization without a subscription a complimentary one.'

    def handle(self, *args, **options):
        created = create_courtesy_subscriptions(Organization, Subscription, Plan)
        self.stdout.write(f'{created} subscription(s) created.')
