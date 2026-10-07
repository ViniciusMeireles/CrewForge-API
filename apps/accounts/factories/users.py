import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from factory.django import DjangoModelFactory

User = get_user_model()
DEFAULT_PASSWORD = 'passWord*123'


class UserFactory(DjangoModelFactory):
    username = factory.LazyAttributeSequence(lambda o, n: f'{o.base_username}{n}')
    email = factory.Sequence(lambda n: f'unit_test_user{n}@horologe.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    email_verified_at = factory.LazyFunction(timezone.now)

    class Params:
        base_username = factory.Faker('user_name')

    class Meta:
        model = User
        skip_postgeneration_save = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.password = DEFAULT_PASSWORD
        if create:
            self.set_password(DEFAULT_PASSWORD)
            self.save()
