from django.db.models import QuerySet
from rest_framework.generics import get_object_or_404

from apps.accounts.models.invitation import Invitation
from apps.accounts.models.user import User


def received_invitations(*, user: User) -> QuerySet[Invitation]:
    invitations: QuerySet[Invitation] = (
        Invitation.objects.filter_actives().filter_received_by_user(user=user)
    )
    return invitations


def invitations_by_key(*, user: User | None) -> QuerySet[Invitation]:
    if user and user.email_verified:
        return received_invitations(user=user)
    pending: QuerySet[Invitation] = Invitation.objects.filter_pending()
    return pending


def lock_invitation(*, invitation_pk: str) -> Invitation:
    invitation: Invitation = get_object_or_404(
        Invitation.objects.select_for_update(of=('self',)).filter_actives(),
        pk=invitation_pk,
    )
    return invitation
