import factory
from django.utils.text import slugify
from factory.django import DjangoModelFactory

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.models.organization import Organization, OrganizationProfile
from apps.generics.factories.mixins import ModelFactoryMixin


class OrganizationFactory(ModelFactoryMixin, DjangoModelFactory):
    name = factory.Faker('company')
    slug = factory.LazyAttribute(lambda o: slugify(o.name))

    class Meta:
        model = Organization
        skip_postgeneration_save = True

    @factory.post_generation
    def owner(self, create, extracted, **kwargs):
        """Create an owner for the organization if requested."""
        if not create:
            return

        from apps.accounts.factories.members import MemberFactory
        from apps.accounts.factories.users import UserFactory

        owner_user = UserFactory()
        self.owner = MemberFactory(
            user=owner_user, organization=self, role=MemberRoleChoices.OWNER.value
        )
        self.save()


class OrganizationProfileFactory(ModelFactoryMixin, DjangoModelFactory):
    organization = factory.SubFactory(OrganizationFactory)
    website = factory.Faker('url')
    description = factory.Faker('text')

    class Meta:
        model = OrganizationProfile
