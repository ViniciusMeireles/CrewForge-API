from django.test import TestCase
from django_filters import filterset

from apps.accounts.factories.organizations import OrganizationFactory
from apps.generics.utils.filters import StableOrderingFilter
from apps.teams.factories.teams import TeamFactory
from apps.teams.models.team import Team


class _TeamFilter(filterset.FilterSet):
    order_by = StableOrderingFilter(fields=['name', 'id'])

    class Meta:
        model = Team
        fields = []


def _ordering(params):
    return list(_TeamFilter(params, queryset=Team.objects.all()).qs.query.order_by)


class StableOrderingFilterTestCase(TestCase):
    def test_appends_primary_key_as_tiebreaker(self):
        self.assertEqual(_ordering({'order_by': 'name'}), ['name', 'pk'])
        self.assertEqual(_ordering({'order_by': '-name'}), ['-name', 'pk'])

    def test_keeps_explicit_primary_key_ordering(self):
        self.assertEqual(_ordering({'order_by': '-id'}), ['-id'])
        self.assertEqual(_ordering({'order_by': 'name,id'}), ['name', 'id'])

    def test_without_ordering_keeps_default(self):
        self.assertEqual(
            _TeamFilter({}, queryset=Team.objects.all()).qs.query.order_by, ()
        )

    def test_ties_are_returned_in_primary_key_order(self):
        teams = [
            TeamFactory(organization=OrganizationFactory(), name='Same')
            for _ in range(3)
        ]
        ids = list(
            _TeamFilter({'order_by': 'name'}, queryset=Team.objects.all())
            .qs.filter(name='Same')
            .values_list('pk', flat=True)
        )
        self.assertEqual(ids, sorted(t.pk for t in teams))
