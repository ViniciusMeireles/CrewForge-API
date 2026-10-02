import factory

from apps.generics.factories.mixins import ModelFactoryMixin
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.models.team_member import TeamMember


class TeamMemberFactory(ModelFactoryMixin):
    team = factory.SubFactory(
        'apps.teams.factories.teams.TeamFactory',
        organization=factory.SelfAttribute('..organization'),
    )
    member = factory.SubFactory(
        'apps.accounts.factories.members.MemberFactory',
        organization=factory.SelfAttribute('..organization'),
    )
    role = TeamMemberRoleChoices.MEMBER

    class Meta:
        model = TeamMember

    class Params:
        organization = factory.SubFactory(
            'apps.accounts.factories.organizations.OrganizationFactory'
        )
