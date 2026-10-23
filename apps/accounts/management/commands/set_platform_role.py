from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError
from django.db.models import Q

from apps.accounts.choices import PlatformRoleChoices
from apps.accounts.utils.platform_role import set_platform_role


class Command(BaseCommand):
    help = 'Grant or change the platform role of a user (none, support, admin).'

    def add_arguments(self, parser):
        parser.add_argument('user', help='Username or email of the user.')
        parser.add_argument('role', choices=PlatformRoleChoices.values)

    def handle(self, *args, **options):
        identifier = options['user']
        users = get_user_model().objects.filter(
            Q(username=identifier) | Q(email__iexact=identifier)
        )
        if users.count() != 1:
            raise CommandError(f'No single user matches {identifier!r}.')
        user = users.get()
        if set_platform_role(user, options['role']):
            self.stdout.write(
                self.style.SUCCESS(f'{user.username} is now {user.platform_role}.')
            )
        else:
            self.stdout.write(f'{user.username} already is {user.platform_role}.')
