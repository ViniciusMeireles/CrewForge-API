from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.teams.factories.teams import TeamFactory
from apps.teams.models.team import Team


class TeamModelTestCase(TestCase):
    def test_str(self):
        team = TeamFactory()
        self.assertEqual(str(team), team.name)

    def test_filter_actives(self):
        TeamFactory(is_active=True)
        TeamFactory(is_active=False)
        self.assertEqual(Team.objects.filter_actives().count(), 1)

    def test_get_or_none_found(self):
        team = TeamFactory()
        result = Team.objects.get_or_none(id=team.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, team.id)

    def test_get_or_none_not_found(self):
        result = Team.objects.get_or_none(id=99999)
        self.assertIsNone(result)

    def test_default_values(self):
        team = TeamFactory()
        self.assertTrue(team.is_active)

    def test_ordering(self):
        TeamFactory.create_batch(size=3)
        teams = list(Team.objects.all())
        team_ids = [t.id for t in teams]
        self.assertEqual(team_ids, sorted(team_ids, reverse=True))

    def test_unique_slug_per_org(self):
        org = OrganizationFactory()
        team = TeamFactory(organization=org)
        with self.assertRaises(IntegrityError):
            TeamFactory(organization=org, slug=team.slug)

    def test_same_slug_different_orgs(self):
        team = TeamFactory()
        with self.assertRaises(IntegrityError):
            TeamFactory(slug=team.slug)
