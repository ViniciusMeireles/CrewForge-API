from typing import TYPE_CHECKING

from django.db import models
from django.utils.functional import classproperty
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from apps.accounts.models.member import Member


class MemberRoleChoices(models.TextChoices):
    OWNER = 'owner', _('Owner')
    ADMIN = 'admin', _('Admin')
    MANAGER = 'manager', _('Manager')
    MEMBER = 'member', _('Member')


class StoredFileAccess(models.TextChoices):
    OWNERS_ORGANIZATION = 'owners_organization', _('Owners of Organization')
    ADMINS_ORGANIZATION = 'admins_organization', _('Admins of Organization')
    MANAGERS_ORGANIZATION = 'managers_organization', _('Managers of Organization')
    MEMBERS_ORGANIZATION = 'members_organization', _('Members of Organization')
    OWNER = 'owner', _('Owner')
    PUBLIC = 'public', _('Public')

    @classproperty
    def organization_accesses(cls) -> list[StoredFileAccess]:
        return [
            cls.MEMBERS_ORGANIZATION,
            cls.MANAGERS_ORGANIZATION,
            cls.ADMINS_ORGANIZATION,
            cls.OWNERS_ORGANIZATION,
        ]

    @classproperty
    def permissions_for_public(cls) -> list[StoredFileAccess]:
        return [StoredFileAccess.PUBLIC]

    @classproperty
    def permissions_for_owner(cls) -> list[StoredFileAccess]:
        return [StoredFileAccess.OWNER] + cls.permissions_for_public

    @classproperty
    def permissions_for_owner_organization_updating(cls) -> list[StoredFileAccess]:
        return [StoredFileAccess.OWNERS_ORGANIZATION] + cls.permissions_for_owner

    @classproperty
    def permissions_for_admin_organization_updating(cls) -> list[StoredFileAccess]:
        return [
            StoredFileAccess.ADMINS_ORGANIZATION
        ] + cls.permissions_for_owner_organization_updating

    @classproperty
    def permissions_for_manager_organization_updating(cls) -> list[StoredFileAccess]:
        return [
            StoredFileAccess.MANAGERS_ORGANIZATION
        ] + cls.permissions_for_admin_organization_updating

    @classproperty
    def permissions_for_member_organization_updating(cls) -> list[StoredFileAccess]:
        return [
            StoredFileAccess.MEMBERS_ORGANIZATION
        ] + cls.permissions_for_manager_organization_updating

    @classproperty
    def permissions_levels_updating(
        cls,
    ) -> dict[StoredFileAccess, list[StoredFileAccess]]:
        public = cls.permissions_for_public
        owner = cls.permissions_for_owner
        owner_organization = cls.permissions_for_owner_organization_updating
        admin_organization = cls.permissions_for_admin_organization_updating
        manager_organization = cls.permissions_for_manager_organization_updating
        member_organization = cls.permissions_for_member_organization_updating
        return {
            cls.PUBLIC: public,
            cls.OWNER: owner,
            cls.OWNERS_ORGANIZATION: owner_organization,
            cls.ADMINS_ORGANIZATION: admin_organization,
            cls.MANAGERS_ORGANIZATION: manager_organization,
            cls.MEMBERS_ORGANIZATION: member_organization,
        }

    @classproperty
    def permissions_for_member_organization_viewing(cls) -> list[StoredFileAccess]:
        return [
            StoredFileAccess.MEMBERS_ORGANIZATION,
        ] + cls.permissions_for_owner

    @classproperty
    def permissions_for_manager_organization_viewing(cls) -> list[StoredFileAccess]:
        return [
            StoredFileAccess.MANAGERS_ORGANIZATION,
        ] + cls.permissions_for_member_organization_viewing

    @classproperty
    def permissions_for_admin_organization_viewing(cls) -> list[StoredFileAccess]:
        return [
            StoredFileAccess.ADMINS_ORGANIZATION,
        ] + cls.permissions_for_manager_organization_viewing

    @classproperty
    def permissions_for_owner_organization_viewing(cls) -> list[StoredFileAccess]:
        return [
            StoredFileAccess.OWNERS_ORGANIZATION,
        ] + cls.permissions_for_admin_organization_viewing

    @classproperty
    def permissions_levels_viewing(
        cls,
    ) -> dict[StoredFileAccess, list[StoredFileAccess]]:
        public = cls.permissions_for_public
        owner = cls.permissions_for_owner
        owner_organization = cls.permissions_for_owner_organization_viewing
        admin_organization = cls.permissions_for_admin_organization_viewing
        manager_organization = cls.permissions_for_manager_organization_viewing
        member_organization = cls.permissions_for_member_organization_viewing
        return {
            cls.PUBLIC: public,
            cls.OWNER: owner,
            cls.OWNERS_ORGANIZATION: owner_organization,
            cls.ADMINS_ORGANIZATION: admin_organization,
            cls.MANAGERS_ORGANIZATION: manager_organization,
            cls.MEMBERS_ORGANIZATION: member_organization,
        }

    @classmethod
    def max_org_level(cls, member: 'Member | None') -> StoredFileAccess | None:
        if not member:
            return None
        if member.has_owner_permission:
            return StoredFileAccess.OWNERS_ORGANIZATION
        elif member.has_admin_permission:
            return StoredFileAccess.ADMINS_ORGANIZATION
        elif member.has_manager_permission:
            return StoredFileAccess.MANAGERS_ORGANIZATION
        elif member.has_member_permission:
            return StoredFileAccess.MEMBERS_ORGANIZATION
        return None
