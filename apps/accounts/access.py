from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from apps.accounts.choices import MemberRoleChoices, StoredFileAccess

if TYPE_CHECKING:
    from apps.accounts.models.member import Member


class Action(StrEnum):
    AUDIT_READ = 'audit.read'
    FILE_ACCESS = 'file.access'
    INVITATION_CHANGE = 'invitation.change'
    INVITATION_MANAGE = 'invitation.manage'
    MEMBER_READ = 'member.read'
    MEMBER_REMOVE = 'member.remove'
    MEMBER_UPDATE = 'member.update'
    ORGANIZATION_RESOURCE_WRITE = 'organization.resource_write'
    ORGANIZATION_SETTINGS = 'organization.settings'
    ORGANIZATION_UPDATE = 'organization.update'
    TEAM_MEMBER_CHANGE = 'team_member.change'
    TEAM_MEMBER_REMOVE = 'team_member.remove'
    TEAM_READ = 'team.read'
    TEAM_WRITE = 'team.write'


ROLE_RANK: dict[str, int] = {
    MemberRoleChoices.MEMBER: 1,
    MemberRoleChoices.MANAGER: 2,
    MemberRoleChoices.ADMIN: 3,
    MemberRoleChoices.OWNER: 4,
}

MINIMUM_ROLE: dict[Action, str] = {
    Action.AUDIT_READ: MemberRoleChoices.ADMIN,
    Action.INVITATION_MANAGE: MemberRoleChoices.ADMIN,
    Action.MEMBER_READ: MemberRoleChoices.MEMBER,
    Action.ORGANIZATION_RESOURCE_WRITE: MemberRoleChoices.ADMIN,
    Action.ORGANIZATION_SETTINGS: MemberRoleChoices.OWNER,
    Action.TEAM_READ: MemberRoleChoices.MEMBER,
    Action.TEAM_WRITE: MemberRoleChoices.MANAGER,
}

FILE_ACCESS_ROLE: dict[str, str] = {
    StoredFileAccess.MEMBERS_ORGANIZATION: MemberRoleChoices.MEMBER,
    StoredFileAccess.MANAGERS_ORGANIZATION: MemberRoleChoices.MANAGER,
    StoredFileAccess.ADMINS_ORGANIZATION: MemberRoleChoices.ADMIN,
    StoredFileAccess.OWNERS_ORGANIZATION: MemberRoleChoices.OWNER,
}


def has_role(actor: Member, role: str) -> bool:
    return actor.is_active and ROLE_RANK.get(actor.role, 0) >= ROLE_RANK[role]


def _is_own_active_member(actor: Member, target: Member) -> bool:
    return actor.user_id == target.user_id and target.is_active


def _can_remove_member(actor: Member, target: Member) -> bool:
    return _is_own_active_member(actor, target) or has_role(
        actor, MemberRoleChoices.ADMIN
    )


def _can_update_member(actor: Member, target: Member) -> bool:
    if _is_own_active_member(actor, target):
        return True
    required = (
        MemberRoleChoices.OWNER
        if target.role == MemberRoleChoices.OWNER
        else MemberRoleChoices.ADMIN
    )
    return has_role(actor, required)


def _can_change_invitation(actor: Member, target: Any) -> bool:
    return has_role(actor, MemberRoleChoices.OWNER) or (
        target.role in (MemberRoleChoices.MANAGER, MemberRoleChoices.MEMBER)
        and has_role(actor, MemberRoleChoices.ADMIN)
    )


def _can_update_organization(actor: Member, target: Any) -> bool:
    return has_role(actor, MemberRoleChoices.OWNER) and actor.organization == target


def _can_access_file(actor: Member, target: str) -> bool:
    role = FILE_ACCESS_ROLE.get(target)
    return role is not None and has_role(actor, role)


def _can_change_team_member(actor: Member, target: Any) -> bool:
    from apps.teams.choices import TeamMemberRoleChoices

    return target.member_id != actor.id and target.role in (
        TeamMemberRoleChoices.assignable_by(actor, target.team)
    )


def _can_remove_team_member(actor: Member, target: Any) -> bool:
    return target.member_id == actor.id or _can_change_team_member(actor, target)


TARGET_RULES: dict[Action, Callable[[Member, Any], bool]] = {
    Action.FILE_ACCESS: _can_access_file,
    Action.INVITATION_CHANGE: _can_change_invitation,
    Action.MEMBER_REMOVE: _can_remove_member,
    Action.MEMBER_UPDATE: _can_update_member,
    Action.ORGANIZATION_UPDATE: _can_update_organization,
    Action.TEAM_MEMBER_CHANGE: _can_change_team_member,
    Action.TEAM_MEMBER_REMOVE: _can_remove_team_member,
}


def authorize(actor: Member | None, action: Action, target: Any = None) -> bool:
    if actor is None or not actor.is_active:
        return False
    if target is not None and action in TARGET_RULES:
        return TARGET_RULES[action](actor, target)
    if action in MINIMUM_ROLE:
        return has_role(actor, MINIMUM_ROLE[action])
    return False
