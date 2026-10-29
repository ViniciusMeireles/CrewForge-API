from datetime import timezone

import factory
from django.utils import timezone as django_timezone

from apps.accounts.choices import InvitationStatusChoices, MemberRoleChoices
from apps.accounts.models.invitation import Invitation
from apps.generics.factories.mixins import ModelFactoryMixin


def _status(invitation) -> str:
    if invitation.is_accepted:
        return InvitationStatusChoices.ACCEPTED
    if invitation.is_declined:
        return InvitationStatusChoices.DECLINED
    if invitation.is_expired:
        return InvitationStatusChoices.EXPIRED
    return InvitationStatusChoices.PENDING


def _date_for(status: str):
    return lambda invitation: (
        django_timezone.now() if invitation.status == status else None
    )


class InvitationFactory(ModelFactoryMixin):
    email = factory.Sequence(lambda n: f'unit_test_invite{n}@example.com')
    status = factory.LazyAttribute(_status)
    accepted_at = factory.LazyAttribute(_date_for(InvitationStatusChoices.ACCEPTED))
    declined_at = factory.LazyAttribute(_date_for(InvitationStatusChoices.DECLINED))
    expired_at = factory.Faker('future_datetime', tzinfo=timezone.utc)
    role = MemberRoleChoices.MEMBER
    organization = factory.SubFactory(
        factory='apps.accounts.factories.organizations.OrganizationFactory',
    )

    class Params:
        is_accepted = False
        is_declined = False
        is_expired = False

    class Meta:
        model = Invitation
        skip_postgeneration_save = True
