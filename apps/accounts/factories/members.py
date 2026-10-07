import factory

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.users import UserFactory
from apps.accounts.models.member import Member
from apps.generics.factories.mixins import ModelFactoryMixin


class MemberFactory(ModelFactoryMixin):
    """Factory for creating Member instances."""

    nickname = factory.LazyAttributeSequence(lambda o, n: f'{o.base_nickname}{n}')
    user = factory.SubFactory(UserFactory)
    organization = factory.SubFactory(
        factory='apps.accounts.factories.organizations.OrganizationFactory',
    )
    role = MemberRoleChoices.MEMBER

    class Params:
        base_nickname = factory.Faker('user_name')

    class Meta:
        model = Member
