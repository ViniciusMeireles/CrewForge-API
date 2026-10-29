import factory
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.models.organization import Organization, OrganizationProfile
from apps.generics.factories.mixins import ModelFactoryMixin


class OrganizationFactory(ModelFactoryMixin):
    name = factory.LazyAttributeSequence(lambda o, n: f'{o.base_name} {n}')
    slug = factory.LazyAttribute(lambda o: slugify(o.name))

    class Params:
        base_name = factory.Faker('company')
        suspended = factory.Trait(
            status='suspended',
            suspended_at=factory.LazyFunction(timezone.now),
            suspension_reason='Chargeback under investigation',
        )

    class Meta:
        model = Organization
        skip_postgeneration_save = True

    profile = factory.RelatedFactory(
        'apps.accounts.factories.organizations.OrganizationProfileFactory',
        factory_related_name='organization',
    )

    @factory.post_generation
    def owner(self, create, extracted, **kwargs):
        """Create an owner for the organization if requested."""
        if not create:
            return

        from apps.accounts.factories.members import MemberFactory
        from apps.accounts.factories.users import UserFactory

        MemberFactory(
            user=UserFactory(), organization=self, role=MemberRoleChoices.OWNER.value
        )


class OrganizationProfileFactory(ModelFactoryMixin):
    organization = factory.SubFactory(OrganizationFactory, profile=None)
    website = factory.Faker('url')
    description = factory.Faker('text')

    class Meta:
        model = OrganizationProfile
