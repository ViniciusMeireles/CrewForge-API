from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.expressions import Case, Value, When
from django.db.models.fields.generated import GeneratedField
from django.db.models.functions import Concat
from django.utils.translation import gettext_lazy as _

from apps.accounts.managers.user import UserManager
from apps.generics.models.abstracts import BaseModel


def _get_user_full_name_expression() -> models.Expression:
    """
    Define the full name expression for the user model.
    This is used to generate the full name of the user based on
    the first name, last name, and username.
    """
    first_name = 'first_name'
    last_name = 'last_name'
    username = 'username'
    return Case(
        When(
            condition=models.Q(
                ~models.Q(**{first_name: ''}),
                ~models.Q(**{last_name: ''}),
                **{f'{first_name}__isnull': False},
                **{f'{last_name}__isnull': False},
            ),
            then=Concat(
                first_name,
                Value(' '),
                last_name,
            ),
        ),
        When(
            condition=models.Q(
                ~models.Q(**{last_name: ''}),
                **{f'{last_name}__isnull': False},
            ),
            then=last_name,
        ),
        When(
            condition=models.Q(
                ~models.Q(**{first_name: ''}),
                **{f'{first_name}__isnull': False},
            ),
            then=first_name,
        ),
        default=models.F(username),
        output_field=models.CharField(),
    )


class User(AbstractUser, BaseModel):
    organizations = models.ManyToManyField(
        to='accounts.Organization',
        related_name='users',
        verbose_name=_('Organizations'),
        help_text=_('Organizations to which the user belongs'),
        through='accounts.Member',
        through_fields=('user', 'organization'),
    )
    full_name = GeneratedField(
        expression=_get_user_full_name_expression(),
        output_field=models.CharField(max_length=300),
        db_persist=True,
        verbose_name=_('Full Name'),
        help_text=_('Full name of the user'),
    )

    objects = UserManager()

    @property
    def active_organizations(self):
        from apps.accounts.models.organization import Organization

        return Organization.objects.filter(
            members__user=self,
            members__is_active=True,
            is_active=True,
        )
