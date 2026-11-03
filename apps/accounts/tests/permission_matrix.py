from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory

ANONYMOUS = 'anonymous'
NO_SESSION = 'no_session'
OWNER = 'owner'
ADMIN = 'admin'
MANAGER = 'manager'
MEMBER = 'member'
INACTIVE = 'inactive'
OTHER_ORGANIZATION = 'other_organization'

ROLES = {
    OWNER: MemberRoleChoices.OWNER,
    ADMIN: MemberRoleChoices.ADMIN,
    MANAGER: MemberRoleChoices.MANAGER,
    MEMBER: MemberRoleChoices.MEMBER,
}
ACTORS = (ANONYMOUS, NO_SESSION, *ROLES, INACTIVE, OTHER_ORGANIZATION)


@dataclass(frozen=True)
class Action:
    """One request of the matrix; ``url`` and ``data`` receive the test case."""

    method: str
    url: Callable[[Any], str]
    data: Callable[[Any], dict] | None = None


class PermissionMatrixMixin:
    """Run ``matrix`` (actor -> action -> status) as subtests on ``organization``.

    Every cell runs in a rolled-back savepoint, so objects created by the URL or
    payload builders and changes made by the request never leak between cells.
    """

    actions: dict[str, Action] = {}
    matrix: dict[str, dict[str, int]] = {}
    inactive_role = MemberRoleChoices.ADMIN

    def authenticate_as(self, actor: str) -> None:
        self.client.logout()
        self.client.force_authenticate(user=None)
        if actor == ANONYMOUS:
            return
        if actor == NO_SESSION:
            self.client.force_authenticate(user=self.organization.owner.user)
        elif actor == OWNER:
            self.client.force_authenticate(member=self.organization.owner)
        elif actor in ROLES:
            member = MemberFactory(organization=self.organization, role=ROLES[actor])
            self.client.force_authenticate(member=member)
        elif actor == INACTIVE:
            member = MemberFactory(
                organization=self.organization,
                role=self.inactive_role,
                is_active=False,
            )
            self.client.force_authenticate(member=member)
        elif actor == OTHER_ORGANIZATION:
            self.client.force_authenticate(member=OrganizationFactory().owner)
        else:
            raise ValueError(f'Unknown actor {actor!r}; expected one of {ACTORS}')

    def request_action(self, name: str):
        action = self.actions[name]
        kwargs = {'format': 'json'}
        if action.data:
            kwargs['data'] = action.data(self)
        return getattr(self.client, action.method)(action.url(self), **kwargs)

    def test_permission_matrix(self):
        self.assertTrue(self.matrix, 'Declare the permission matrix')
        for actor, row in self.matrix.items():
            for name, expected in row.items():
                with self.subTest(actor=actor, action=name), transaction.atomic():
                    self.authenticate_as(actor)
                    response = self.request_action(name)
                    self.assertEqual(
                        response.status_code,
                        expected,
                        f'{actor} {name}: {getattr(response, "data", None)}',
                    )
                    transaction.set_rollback(True)
