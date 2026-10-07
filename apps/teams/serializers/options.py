from apps.accounts.utils.requests import get_member, get_organization_id
from apps.teams.choices import TeamMemberRoleChoices
from apps.teams.models.team import Team

TEAM_ID_PARAM = 'team_id'


def get_context_team(context: dict) -> Team | None:
    """
    Team given by ``?team_id=<id>`` on an options route, limited to the active
    teams of the session organization. Kept in the serializer context, so it is
    looked up once per response.
    """
    if '_options_team' in context:
        return context['_options_team']
    request = context.get('request')
    params = getattr(request, 'query_params', None) or {}
    team = None
    raw_id = params.get(TEAM_ID_PARAM, '')
    if (
        raw_id.isascii()
        and raw_id.isdigit()
        and (organization_id := get_organization_id(request))
    ):
        team = Team.objects.filter(
            pk=int(raw_id), organization_id=organization_id, is_active=True
        ).first()
    context['_options_team'] = team
    return team


def assignable_team_role_choices(choices: list, context: dict) -> list:
    """
    ``choices_filter`` that keeps the team roles the requester may assign in the
    ``?team_id`` team (see ``TeamMemberRoleChoices.assignable_by``).
    """
    if (allowed := context.get('_assignable_team_roles')) is None:
        member = get_member(context.get('request'))
        allowed = context['_assignable_team_roles'] = set(
            TeamMemberRoleChoices.assignable_by(member, get_context_team(context))
        )
    return [choice for choice in choices if choice['value'] in allowed]


def exclude_team_members(queryset, context: dict):
    """``queryset_filter`` hiding members already active in the ``?team_id`` team."""
    if (team := get_context_team(context)) is None:
        return queryset
    return queryset.exclude(
        pk__in=team.members.filter(is_active=True).values('member_id')
    )
