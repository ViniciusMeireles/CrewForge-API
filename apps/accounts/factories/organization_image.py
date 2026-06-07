import factory
from factory.django import DjangoModelFactory

from apps.accounts.choices import OrganizationImageTypeChoices
from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.models.organization import OrganizationImage
from apps.generics.factories.mixins import ModelFactoryMixin


class OrganizationImageFactory(ModelFactoryMixin, DjangoModelFactory):
    profile = factory.SubFactory(
        'apps.accounts.factories.organizations.OrganizationProfileFactory',
    )
    image_type = OrganizationImageTypeChoices.LOGO
    image = factory.SubFactory(
        StoredFileFactory,
        organization=factory.SelfAttribute('..profile.organization'),
        public=True,
    )

    class Meta:
        model = OrganizationImage
