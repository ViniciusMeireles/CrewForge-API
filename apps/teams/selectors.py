from django.db.models import QuerySet

from apps.teams.models.team import Team


def teams_with_member_count(queryset: QuerySet[Team]) -> QuerySet[Team]:
    return queryset.annotate(member_count=Team.member_count_expression()).order_by(
        '-id'
    )
