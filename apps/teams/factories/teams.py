import factory
from django.utils.text import slugify

from apps.generics.factories.mixins import ModelFactoryMixin
from apps.teams.models.team import Team


class TeamFactory(ModelFactoryMixin):
    name = factory.LazyAttributeSequence(lambda o, n: f'{o.base_name} {n}')
    slug = factory.LazyAttribute(lambda o: slugify(o.name))
    description = factory.Faker('text', max_nb_chars=200)
    organization = factory.SubFactory(
        factory='apps.accounts.factories.organizations.OrganizationFactory',
    )

    class Params:
        base_name = factory.Faker('company')

    class Meta:
        model = Team
