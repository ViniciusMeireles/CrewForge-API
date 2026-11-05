from django.utils import timezone
from rest_framework.request import Request

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.accounts.models.user import User
from apps.accounts.utils.security_log import log_security_event


def create_owner_membership(*, organization: Organization, user: User) -> Member:
    return Member.objects.create(
        user=user,
        organization=organization,
        role=MemberRoleChoices.OWNER,
        created_by=user,
        updated_by=user,
    )


def record_organization_login(*, organization: Organization, request: Request) -> None:
    log_security_event('organization.login', request, organization_id=organization.id)


def touch_last_login(*, member: Member) -> None:
    member.last_login_at = timezone.now()
    member.save(update_fields=['last_login_at'])
