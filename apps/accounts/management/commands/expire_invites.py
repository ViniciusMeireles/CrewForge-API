from django.core.management import BaseCommand

from apps.accounts.choices import InvitationStatusChoices
from apps.accounts.models.invitation import Invitation


class Command(BaseCommand):
    help = 'Expire all pending invites that are past their expiration date.'

    def handle(self, *args, **options):
        from django.utils import timezone

        expired_invites = Invitation.objects.filter(
            status=InvitationStatusChoices.PENDING,
            expired_at__lte=timezone.now(),
        )

        count_expired = expired_invites.update(status=InvitationStatusChoices.EXPIRED)
        self.stdout.write(self.style.SUCCESS(f'Expired {count_expired} invites.'))
