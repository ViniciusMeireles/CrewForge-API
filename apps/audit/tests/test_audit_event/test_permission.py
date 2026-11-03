from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.accounts.tests.permission_matrix import (
    ADMIN,
    ANONYMOUS,
    INACTIVE,
    MANAGER,
    MEMBER,
    NO_SESSION,
    OTHER_ORGANIZATION,
    OWNER,
    Action,
    PermissionMatrixMixin,
)
from apps.audit.factories.audit_event import AuditEventFactory
from apps.audit.tests.mixins import DETAIL_URL, LIST_URL, AuditAPITestCaseMixin


def _detail(case):
    event = AuditEventFactory(
        organization=case.organization, actor_member=case.organization.owner
    )
    return reverse(DETAIL_URL, args=[event.pk])


class AuditEventPermissionMatrixTestCase(
    PermissionMatrixMixin, APITestCaseMixin, APITestCase
):
    actions = {
        'list': Action('get', lambda case: reverse(LIST_URL)),
        'retrieve': Action('get', _detail),
    }
    matrix = {
        ANONYMOUS: {'list': 401, 'retrieve': 401},
        NO_SESSION: {'list': 403},
        INACTIVE: {'list': 403},
        OWNER: {'list': 200, 'retrieve': 200},
        ADMIN: {'list': 200, 'retrieve': 200},
        MANAGER: {'list': 403, 'retrieve': 403},
        MEMBER: {'list': 403},
        OTHER_ORGANIZATION: {'retrieve': 404},
    }

    def setUp(self):
        self.organization = OrganizationFactory()


class AuditEventPermissionTestCase(AuditAPITestCaseMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.event = AuditEventFactory(
            organization=self.organization, actor_member=self.owner
        )

    def member_with(self, role):
        return MemberFactory(organization=self.organization, role=role)

    def session_access(self):
        return self.client.get('/api/accounts/session/').data['member']['access']

    def test_cross_org_owner_does_not_see_events(self):
        other_owner = MemberFactory(role=MemberRoleChoices.OWNER, replace_owner=True)
        self.client.force_authenticate(member=other_owner)
        self.clear_events()
        self.assertEqual(self.list_events().data['count'], 0)
        self.assertEqual(
            self.retrieve_event(self.event).status_code, http_status.HTTP_404_NOT_FOUND
        )

    def test_session_access_flags_audit_by_role(self):
        for role, expected in (
            (MemberRoleChoices.OWNER, True),
            (MemberRoleChoices.ADMIN, True),
            (MemberRoleChoices.MANAGER, False),
            (MemberRoleChoices.MEMBER, False),
        ):
            with self.subTest(role=role):
                member = (
                    self.owner
                    if role == MemberRoleChoices.OWNER
                    else self.member_with(role)
                )
                self.client.force_authenticate(member=member)
                self.assertIs(self.session_access()['audit'], expected)

    def test_member_deactivated_during_session_is_refused(self):
        admin = self.member_with(MemberRoleChoices.ADMIN)
        self.client.force_authenticate(member=admin)
        admin.inactivate()
        self.assertEqual(self.list_events().status_code, http_status.HTTP_403_FORBIDDEN)
