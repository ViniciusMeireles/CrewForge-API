import factory
from django.utils.text import slugify

from apps.generics.factories import ModelFactoryMixin
from apps.{app}.models.{resource} import {Resource}


class {Resource}Factory(ModelFactoryMixin, factory.django.DjangoModelFactory):
    name = factory.Faker('company')
    slug = factory.LazyAttribute(lambda o: slugify(o.name))
    {extra_fields}
    organization = factory.SubFactory(
        'apps.accounts.factories.organizations.OrganizationFactory'
    )

    class Meta:
        model = {Resource}

    class Params:
        {traits}
