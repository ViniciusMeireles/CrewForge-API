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
        other_team = TeamFactory(slug=team.slug)
        self.assertNotEqual(team.organization_id, other_team.organization_id)

    def test_unique_slug_per_org_allows_reuse_after_soft_delete(self):
        org = OrganizationFactory()
        team = TeamFactory(organization=org, slug='my-team')
        team.inactivate()
        new_team = TeamFactory(organization=org, slug='my-team')
        self.assertNotEqual(team.id, new_team.id)

    def test_unique_name_per_org(self):
        org = OrganizationFactory()
        TeamFactory(organization=org, name='Backend', slug='backend-1')
        with self.assertRaises(IntegrityError):
            TeamFactory(organization=org, name='Backend', slug='backend-2')

    def test_unique_name_per_org_allows_reuse_after_soft_delete(self):
        org = OrganizationFactory()
        team = TeamFactory(organization=org, name='Backend')
        team.inactivate()
        new_team = TeamFactory(organization=org, name='Backend')
        self.assertNotEqual(team.id, new_team.id)
