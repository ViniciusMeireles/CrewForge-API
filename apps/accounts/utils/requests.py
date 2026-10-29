from rest_framework.request import Request

from apps.accounts.choices import OrganizationStatusChoices
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization

MEMBER_CACHE_ATTRIBUTE = '_auth_member_cache'


def get_session_organization_id(request: Request) -> int | None:
    """The organization ID stored in the session, not checked against the user."""
    if not request or not request.user.is_authenticated or not request.user.is_active:
        return None
    return request.session.get('organization_id')


def get_organization_id(request: Request) -> int | None:
    """The organization ID of the request's active Member, ``None`` without one."""
    member = get_member(request)
    return member.organization_id if member else None


def get_organization(request: Request) -> Organization | None:
    """Get the organization from the request."""
    if not (organization_id := get_organization_id(request)):
        return None
    return Organization.objects.filter(
        members__user=request.user,
        members__is_active=True,
        is_active=True,
        status=OrganizationStatusChoices.ACTIVE,
        id=organization_id,
    ).get_or_none()


def get_member(request: Request) -> Member | None:
    """Get the member from the request, once per request, User and Organization."""
    if not request:
        return None
    user = request.user
    if not user.is_authenticated:
        return None
    if not user.is_active:
        return None
    if not (organization_id := get_session_organization_id(request)):
        return None
    key = (user.pk, organization_id)
    cached = getattr(request, MEMBER_CACHE_ATTRIBUTE, None)
    if cached is not None and cached[0] == key:
        return cached[1]
    member = (
        Member.objects.filter_actives()
        .filter(
            user=user,
            organization_id=organization_id,
            organization__status=OrganizationStatusChoices.ACTIVE,
        )
        .get_or_none(organization_id=organization_id)
    )
    setattr(request, MEMBER_CACHE_ATTRIBUTE, (key, member))
    return member


def clear_suspended_organization_context(request: Request) -> int | None:
    """
    Drop the session's Organization when it is suspended (BR-11).

    Returns the id that was dropped, so the caller can refuse the request.
    """
    if not (organization_id := get_session_organization_id(request)):
        return None
    if get_member(request) is not None:
        return None
    if not Organization.objects.filter(
        id=organization_id, status=OrganizationStatusChoices.SUSPENDED
    ).exists():
        return None
    request.session.pop('organization_id', None)
    return organization_id


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
