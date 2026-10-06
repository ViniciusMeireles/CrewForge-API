from django.test import TestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.teams.factories.teams import TeamFactory


class UniqueFakerValuesTestCase(TestCase):
    def test_repeated_faker_values_do_not_collide(self):
        organizations = OrganizationFactory.create_batch(size=2, base_name='Same')
        teams = TeamFactory.create_batch(
            size=2, organization=organizations[0], base_name='Same'
        )
        users = UserFactory.create_batch(size=2, base_username='same')
        for objects, attr in (
            (organizations, 'slug'),
            (teams, 'name'),
            (teams, 'slug'),
            (users, 'username'),
        ):
            with self.subTest(attr=attr):
                values = [getattr(obj, attr) for obj in objects]
                self.assertEqual(len(set(values)), len(values))
