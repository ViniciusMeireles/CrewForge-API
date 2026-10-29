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

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        if kwargs.get('role') == MemberRoleChoices.OWNER and kwargs.get(
            'is_active', True
        ):
            model_class.objects.filter(
                organization=kwargs['organization'],
                role=MemberRoleChoices.OWNER,
                is_active=True,
            ).update(role=MemberRoleChoices.ADMIN)
        return super()._create(model_class, *args, **kwargs)
