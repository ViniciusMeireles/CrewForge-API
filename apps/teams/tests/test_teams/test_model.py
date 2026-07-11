from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.teams.factories.teams import TeamFactory


class TeamModelTestCase(TestCase):
    def test_str(self):
        team = TeamFactory()
        self.assertEqual(str(team), team.name)

    def test_unique_slug_per_org(self):
        org = OrganizationFactory()
        team = TeamFactory(organization=org)
        with self.assertRaises(IntegrityError):
            TeamFactory(organization=org, slug=team.slug)

    def test_same_slug_different_orgs(self):
        team = TeamFactory()
        with self.assertRaises(IntegrityError):
            TeamFactory(slug=team.slug)
