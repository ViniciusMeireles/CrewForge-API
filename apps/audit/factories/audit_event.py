import factory
from factory.django import DjangoModelFactory

from apps.accounts.factories.members import MemberFactory
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.models.audit_event import AuditEvent


class AuditEventFactory(DjangoModelFactory):
    action = AuditActionChoices.TEAM_CREATED
    actor_type = AuditActorTypeChoices.USER
    actor_member = factory.SubFactory(MemberFactory)
    actor_user = factory.LazyAttribute(lambda o: o.actor_member.user)
    actor_label = factory.LazyAttribute(lambda o: o.actor_member.audit_label)
    organization = factory.LazyAttribute(lambda o: o.actor_member.organization)
    target_type = 'team'
    target_id = factory.Sequence(str)
    target_label = factory.Sequence(lambda n: f'Team {n}')
    ip = '127.0.0.1'

    class Meta:
        model = AuditEvent

    class Params:
        account = factory.Trait(
            action=AuditActionChoices.AUTH_LOGIN_SUCCEEDED,
            organization=None,
            actor_member=None,
            actor_user=factory.SubFactory('apps.accounts.factories.users.UserFactory'),
            actor_label=factory.LazyAttribute(lambda o: o.actor_user.username),
            subject_user=factory.LazyAttribute(lambda o: o.actor_user),
            target_type='',
            target_id='',
            target_label='',
        )
