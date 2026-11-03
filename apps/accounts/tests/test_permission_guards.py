from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.accounts.choices import MemberRoleChoices, StoredFileAccess
from apps.accounts.permissions.files import StoredFilePermission
from apps.accounts.permissions.generics import (
    OrganizationAdminObjPermission,
    OrganizationScopedPermission,
)
from apps.accounts.permissions.invitation import InvitationPermission
from apps.accounts.permissions.member import MemberPermission
from apps.accounts.permissions.organization_image import OrganizationImagePermission
from apps.teams.permissions.team_member import TeamMemberPermission

VIEW = SimpleNamespace(action='partial_update')
USER = SimpleNamespace(is_authenticated=True, is_active=True, id=1)


def request(method='PATCH'):
    return SimpleNamespace(method=method, user=USER)


def member(organization_id=1, **flags):
    return SimpleNamespace(
        id=10, organization_id=organization_id, is_active=True, **flags
    )


class StoredFileGuardsTestCase(SimpleTestCase):
    def check(self, auth_member):
        stored_file = SimpleNamespace(
            owner_id=99,
            organization_id=1,
            viewing_permission=StoredFileAccess.ADMINS_ORGANIZATION,
        )
        with mock.patch(
            'apps.accounts.permissions.files.get_member', return_value=auth_member
        ):
            return StoredFilePermission().has_object_permission(
                request('GET'), VIEW, stored_file
            )

    def test_refuses_without_an_active_member(self):
        self.assertFalse(self.check(None))
        self.assertFalse(self.check(SimpleNamespace(is_active=False)))

    def test_refuses_a_member_of_another_organization(self):
        self.assertFalse(self.check(member(organization_id=2)))


class ObjectPermissionGuardsTestCase(SimpleTestCase):
    def scoped(self, allowed):
        return mock.patch.object(
            OrganizationScopedPermission, 'has_object_permission', return_value=allowed
        )

    def test_admin_object_permission_refuses_inactive_members(self):
        with mock.patch(
            'apps.accounts.permissions.generics.get_member', return_value=None
        ):
            self.assertFalse(
                OrganizationAdminObjPermission().has_object_permission(
                    request(), VIEW, SimpleNamespace()
                )
            )

    def test_invitation_refuses_out_of_scope_objects(self):
        with self.scoped(False):
            self.assertFalse(
                InvitationPermission().has_object_permission(
                    request(), VIEW, SimpleNamespace(role=MemberRoleChoices.MEMBER)
                )
            )

    def test_invitation_refuses_without_a_member(self):
        with (
            self.scoped(True),
            mock.patch(
                'apps.accounts.permissions.invitation.get_member', return_value=None
            ),
        ):
            self.assertFalse(
                InvitationPermission().has_object_permission(
                    request(), VIEW, SimpleNamespace(role=MemberRoleChoices.MEMBER)
                )
            )

    def test_member_refuses_out_of_scope_objects(self):
        with self.scoped(False):
            self.assertFalse(
                MemberPermission().has_object_permission(
                    request(), VIEW, SimpleNamespace(role=MemberRoleChoices.MEMBER)
                )
            )

    def test_team_member_refuses_out_of_scope_objects(self):
        with self.scoped(False):
            self.assertFalse(
                TeamMemberPermission().has_object_permission(
                    request(), VIEW, SimpleNamespace(member_id=10)
                )
            )

    def test_team_member_refuses_without_a_member(self):
        with (
            self.scoped(True),
            mock.patch(
                'apps.teams.permissions.team_member.get_member', return_value=None
            ),
        ):
            self.assertFalse(
                TeamMemberPermission().has_object_permission(
                    request(), VIEW, SimpleNamespace(member_id=10)
                )
            )

    def test_organization_image_refuses_when_its_file_is_refused(self):
        with mock.patch.object(
            StoredFilePermission, 'has_object_permission', return_value=False
        ):
            self.assertFalse(
                OrganizationImagePermission().has_object_permission(
                    request('GET'), VIEW, SimpleNamespace(image=SimpleNamespace())
                )
            )
