from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.accounts.access import (
    MINIMUM_ROLE,
    ROLE_RANK,
    TARGET_RULES,
    Action,
    authorize,
    has_role,
)
from apps.accounts.choices import MemberRoleChoices, StoredFileAccess
from apps.accounts.models.member import Member

OWNER = MemberRoleChoices.OWNER
ADMIN = MemberRoleChoices.ADMIN
MANAGER = MemberRoleChoices.MANAGER
MEMBER = MemberRoleChoices.MEMBER
ROLES = (OWNER, ADMIN, MANAGER, MEMBER)

ALLOWED_ROLES = {
    Action.AUDIT_READ: {OWNER, ADMIN},
    Action.INVITATION_MANAGE: {OWNER, ADMIN},
    Action.MEMBER_READ: set(ROLES),
    Action.ORGANIZATION_RESOURCE_WRITE: {OWNER, ADMIN},
    Action.ORGANIZATION_SETTINGS: {OWNER},
    Action.TEAM_READ: set(ROLES),
    Action.TEAM_WRITE: {OWNER, ADMIN, MANAGER},
}

PROPERTIES = {
    'has_audit_access': Action.AUDIT_READ,
    'has_invitations_access': Action.INVITATION_MANAGE,
    'has_members_access': Action.MEMBER_READ,
    'has_organization_settings_access': Action.ORGANIZATION_SETTINGS,
    'has_teams_access': Action.TEAM_READ,
}


def actor(role, **fields) -> Member:
    return Member(id=1, user_id=1, organization_id=1, role=role, **fields)


class AccessPolicyTestCase(SimpleTestCase):
    def test_every_action_has_a_rule(self):
        self.assertEqual(set(Action), set(MINIMUM_ROLE) | set(TARGET_RULES))

    def test_role_table(self):
        for action, allowed in ALLOWED_ROLES.items():
            for role in ROLES:
                with self.subTest(action=action, role=role):
                    self.assertEqual(authorize(actor(role), action), role in allowed)

    def test_nobody_without_an_active_member(self):
        for action in Action:
            with self.subTest(action=action):
                self.assertFalse(authorize(None, action))
                self.assertFalse(authorize(actor(OWNER, is_active=False), action))

    def test_member_properties_agree_with_the_policy(self):
        for name, action in PROPERTIES.items():
            for role in ROLES:
                with self.subTest(property=name, role=role):
                    member = actor(role)
                    self.assertEqual(getattr(member, name), authorize(member, action))

    def test_role_hierarchy(self):
        for role in ROLES:
            for required in ROLES:
                with self.subTest(role=role, required=required):
                    self.assertEqual(
                        has_role(actor(role), required),
                        ROLE_RANK[role] >= ROLE_RANK[required],
                    )

    def test_unknown_role_has_no_access(self):
        self.assertFalse(has_role(actor('guest'), MEMBER))

    def test_target_rules_need_a_target(self):
        for action in TARGET_RULES:
            with self.subTest(action=action):
                self.assertFalse(authorize(actor(OWNER), action))


class MemberTargetRulesTestCase(SimpleTestCase):
    def target(self, role=MEMBER, user_id=2, is_active=True) -> Member:
        return Member(id=2, user_id=user_id, role=role, is_active=is_active)

    def test_removing_needs_admin_or_oneself(self):
        self.assertTrue(authorize(actor(ADMIN), Action.MEMBER_REMOVE, self.target()))
        self.assertFalse(authorize(actor(MANAGER), Action.MEMBER_REMOVE, self.target()))
        self.assertTrue(
            authorize(actor(MEMBER), Action.MEMBER_REMOVE, self.target(user_id=1))
        )

    def test_updating_needs_admin_or_oneself(self):
        self.assertTrue(authorize(actor(ADMIN), Action.MEMBER_UPDATE, self.target()))
        self.assertFalse(authorize(actor(MANAGER), Action.MEMBER_UPDATE, self.target()))
        self.assertTrue(
            authorize(actor(MEMBER), Action.MEMBER_UPDATE, self.target(user_id=1))
        )

    def test_updating_the_owner_needs_the_owner(self):
        target = self.target(role=OWNER)
        self.assertTrue(authorize(actor(OWNER), Action.MEMBER_UPDATE, target))
        self.assertFalse(authorize(actor(ADMIN), Action.MEMBER_UPDATE, target))

    def test_an_inactive_own_record_is_not_oneself(self):
        target = self.target(user_id=1, is_active=False)
        self.assertFalse(authorize(actor(MEMBER), Action.MEMBER_UPDATE, target))


class OtherTargetRulesTestCase(SimpleTestCase):
    def test_invitation_roles(self):
        for role, target_role, expected in (
            (OWNER, OWNER, True),
            (ADMIN, ADMIN, False),
            (ADMIN, MANAGER, True),
            (ADMIN, MEMBER, True),
            (MANAGER, MEMBER, False),
        ):
            with self.subTest(role=role, target_role=target_role):
                invitation = SimpleNamespace(role=target_role)
                self.assertEqual(
                    authorize(actor(role), Action.INVITATION_CHANGE, invitation),
                    expected,
                )

    def test_organization_update_needs_its_owner(self):
        owner = actor(OWNER)
        with mock.patch.object(Member, 'organization', 'mine'):
            self.assertTrue(authorize(owner, Action.ORGANIZATION_UPDATE, 'mine'))
            self.assertFalse(authorize(owner, Action.ORGANIZATION_UPDATE, 'other'))
            self.assertFalse(
                authorize(actor(ADMIN), Action.ORGANIZATION_UPDATE, 'mine')
            )

    def test_file_levels(self):
        for level, role, expected in (
            (StoredFileAccess.MEMBERS_ORGANIZATION, MEMBER, True),
            (StoredFileAccess.MANAGERS_ORGANIZATION, MEMBER, False),
            (StoredFileAccess.MANAGERS_ORGANIZATION, MANAGER, True),
            (StoredFileAccess.ADMINS_ORGANIZATION, MANAGER, False),
            (StoredFileAccess.ADMINS_ORGANIZATION, ADMIN, True),
            (StoredFileAccess.OWNERS_ORGANIZATION, ADMIN, False),
            (StoredFileAccess.OWNERS_ORGANIZATION, OWNER, True),
            (StoredFileAccess.PUBLIC, OWNER, False),
        ):
            with self.subTest(level=level, role=role):
                self.assertEqual(
                    authorize(actor(role), Action.FILE_ACCESS, level), expected
                )

    def test_team_member_rules(self):
        own = SimpleNamespace(member_id=1, role=MEMBER, team=None)
        other = SimpleNamespace(member_id=2, role=MEMBER, team=None)
        manager = actor(MANAGER)
        self.assertFalse(authorize(manager, Action.TEAM_MEMBER_CHANGE, own))
        self.assertTrue(authorize(manager, Action.TEAM_MEMBER_CHANGE, other))
        self.assertTrue(authorize(actor(MEMBER), Action.TEAM_MEMBER_REMOVE, own))
        self.assertFalse(authorize(actor(MEMBER), Action.TEAM_MEMBER_REMOVE, other))
