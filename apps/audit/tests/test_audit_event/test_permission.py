from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.audit.factories.audit_event import AuditEventFactory
from apps.audit.tests.mixins import AuditAPITestCaseMixin


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

    def test_not_authenticated_list(self):
        self.client.logout()
        self.assertEqual(
            self.list_events().status_code, http_status.HTTP_401_UNAUTHORIZED
        )

    def test_not_authenticated_retrieve(self):
        self.client.logout()
        self.assertEqual(
            self.retrieve_event(self.event).status_code,
            http_status.HTTP_401_UNAUTHORIZED,
        )

    def test_without_organization_context(self):
        self.client.logout()
        self.client.force_authenticate(user=self.owner.user)
        self.assertEqual(self.list_events().status_code, http_status.HTTP_403_FORBIDDEN)

    def test_owner_can_list(self):
        self.assertEqual(self.list_events().status_code, http_status.HTTP_200_OK)
        self.assertTrue(self.session_access()['audit'])

    def test_admin_can_list(self):
        self.client.force_authenticate(member=self.member_with(MemberRoleChoices.ADMIN))
        self.assertEqual(self.list_events().status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            self.retrieve_event(self.event).status_code, http_status.HTTP_200_OK
        )
        self.assertTrue(self.session_access()['audit'])

    def test_manager_cannot_list(self):
        self.client.force_authenticate(
            member=self.member_with(MemberRoleChoices.MANAGER)
        )
        self.assertEqual(self.list_events().status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.retrieve_event(self.event).status_code, http_status.HTTP_403_FORBIDDEN
        )
        self.assertFalse(self.session_access()['audit'])

    def test_member_cannot_list(self):
        self.client.force_authenticate(
            member=self.member_with(MemberRoleChoices.MEMBER)
        )
        self.assertEqual(self.list_events().status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.session_access()['audit'])

    def test_not_active_member_list(self):
        admin = self.member_with(MemberRoleChoices.ADMIN)
        self.client.force_authenticate(member=admin)
        admin.inactivate()
        self.assertEqual(self.list_events().status_code, http_status.HTTP_403_FORBIDDEN)

    def test_cross_org_member_retrieve(self):
        other = AuditEventFactory()
        self.assertEqual(
            self.retrieve_event(other).status_code, http_status.HTTP_404_NOT_FOUND
        )

    def test_cross_org_owner_does_not_see_events(self):
        other_owner = MemberFactory(role=MemberRoleChoices.OWNER, replace_owner=True)
        self.client.force_authenticate(member=other_owner)
        self.clear_events()
        self.assertEqual(self.list_events().data['count'], 0)
        self.assertEqual(
            self.retrieve_event(self.event).status_code, http_status.HTTP_404_NOT_FOUND
        )
