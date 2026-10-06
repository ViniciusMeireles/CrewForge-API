from factory.django import DjangoModelFactory


class ModelFactoryMixin(DjangoModelFactory):
    is_active = True

    class Meta:
        abstract = True
