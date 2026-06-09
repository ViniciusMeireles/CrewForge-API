from rest_framework.request import Request

from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization


def get_organization_id(request: Request) -> int | None:
    """Get the organization ID from the request."""
    if not request or not request.user.is_authenticated:
        return None
    return request.session.get('organization_id')


def get_organization(request: Request) -> Organization | None:
    """Get the organization from the request."""
    if not (organization_id := get_organization_id(request)):
        return None
    return request.user.organizations.filter(is_active=True).get_or_none(
        id=organization_id
    )


def get_member(request: Request) -> Member | None:
    """Get the member from the request."""
    if not request:
        return None
    user = request.user
    if not user.is_authenticated:
        return None
    if not (organization_id := request.session.get('organization_id')):
        return None
    return user.members.filter(is_active=True).get_or_none(
        organization_id=organization_id
    )


def is_same_organization_scope(
    obj,
    organization_id: int | None,
    lookup: str = 'organization_id',
    separator: str = '.',
) -> bool:
    """Check whether an object belongs to the given organization scope."""
    if not organization_id:
        return False

    current = obj
    for attr in lookup.split(separator):
        current = getattr(current, attr, None)
        if current is None:
            return False

    return current == organization_id
