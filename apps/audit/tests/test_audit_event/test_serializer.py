from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.users import UserFactory
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.factories.audit_event import AuditEventFactory
from apps.audit.tests.mixins import AuditAPITestCaseMixin

FIELDS = {
    'id',
    'created_at',
    'action',
    'action_display',
    'actor_type',
    'actor',
    'impersonator',
    'organization_id',
    'target_type',
    'target_id',
    'target_label',
    'changes',
    'metadata',
    'ip',
}


class AuditEventSerializerTestCase(AuditAPITestCaseMixin, APITestCase):
    def create_event(self, **kwargs):
        kwargs.setdefault('actor_member', self.owner)
        return AuditEventFactory(organization=self.organization, **kwargs)

    def test_fields(self):
        event = self.create_event()
        response = self.retrieve_event(event)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(set(response.data), FIELDS)

    def test_actor(self):
        event = self.create_event()
        actor = self.retrieve_event(event).data['actor']
        self.assertEqual(
            actor,
            {
                'user_id': self.owner.user_id,
                'member_id': self.owner.pk,
                'label': self.owner.audit_label,
            },
        )

    def test_system_actor_is_null(self):
        event = self.create_event(
            actor_member=None,
            actor_user=None,
            actor_label='',
            actor_type=AuditActorTypeChoices.SYSTEM,
        )
        data = self.retrieve_event(event).data
        self.assertIsNone(data['actor'])
        self.assertEqual(data['actor_type'], 'system')
        self.assertIsNone(data['impersonator'])

    def test_changes_have_field_display(self):
        event = self.create_event(
            action=AuditActionChoices.MEMBER_ROLE_CHANGED,
            target_type='member',
            changes=[{'field': 'role', 'before': 'member', 'after': 'manager'}],
        )
        change = self.retrieve_event(event).data['changes'][0]
        self.assertEqual(
            change,
            {
                'field': 'role',
                'field_display': 'Role',
                'before': 'member',
                'after': 'manager',
            },
        )

    def test_unknown_field_display_falls_back_to_the_field(self):
        event = self.create_event(
            target_type='unknown',
            changes=[{'field': 'color', 'before': None, 'after': 'red'}],
        )
        change = self.retrieve_event(event).data['changes'][0]
        self.assertEqual(change['field_display'], 'color')

    def test_labels_follow_the_request_language(self):
        event = self.create_event(
            action=AuditActionChoices.MEMBER_ROLE_CHANGED,
            target_type='member',
            changes=[{'field': 'role', 'before': 'member', 'after': 'manager'}],
        )
        response = self.client.get(
            self.retrieve_event(event).request['PATH_INFO'],
            HTTP_ACCEPT_LANGUAGE='pt-BR',
        )
        self.assertEqual(response.data['action_display'], 'Cargo do membro alterado')
        self.assertEqual(response.data['changes'][0]['field_display'], 'Função')

    def test_impersonator(self):
        staff = UserFactory()
        event = self.create_event(impersonator=staff)
        self.assertEqual(
            self.retrieve_event(event).data['impersonator'],
            {'user_id': staff.pk, 'label': str(staff)},
        )

    def test_unknown_field_of_a_known_model_falls_back_to_the_field(self):
        event = self.create_event(
            target_type='member',
            changes=[{'field': 'legacy', 'before': 1, 'after': 2}],
        )
        change = self.retrieve_event(event).data['changes'][0]
        self.assertEqual(change['field_display'], 'legacy')
