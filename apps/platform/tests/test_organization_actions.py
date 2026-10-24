from unittest import mock

from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices, OrganizationStatusChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.models.audit_event import AuditEvent
from apps.platform.tests.mixins import PlatformTestMixin

APPLY_ASYNC = 'apps.accounts.tasks.send_email_task.apply_async'


def queued_emails(apply_async) -> list[tuple[str, list[str], dict]]:
    return [
        (
            call.kwargs['kwargs']['email_class_path'].rsplit('.', 1)[-1],
            call.kwargs['kwargs']['recipient_list'],
            call.kwargs['kwargs']['kwargs'],
        )
        for call in apply_async.call_args_list
    ]


class PlatformOrganizationActionTestCase(
    PlatformTestMixin, APITestCaseMixin, APITestCase
):
    def setUp(self):
        self.organization = OrganizationFactory(name='Acme Inc')
        self.owner = self.organization.owner
        self.staff = self.authenticate_staff('admin')

    def url(self, name: str) -> str:
        return reverse(f'platform:organizations-{name}', args=[self.organization.id])

    def post(self, name: str, data=None):
        with mock.patch(APPLY_ASYNC) as apply_async:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url(name), data=data, format='json')
        return response, apply_async

    def test_suspend(self):
        response, apply_async = self.post('suspend', {'reason': '  Chargeback  '})

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['status'], OrganizationStatusChoices.SUSPENDED)
        self.assertEqual(response.data['suspension']['reason'], 'Chargeback')
        self.assertEqual(
            response.data['suspension']['suspended_by']['id'], self.staff.id
        )
        self.organization.refresh_from_db()
        self.assertTrue(self.organization.is_suspended)
        self.assertEqual(
            queued_emails(apply_async),
            [
                (
                    'OrganizationSuspendedEmail',
                    [self.owner.user.email],
                    {'organization_name': 'Acme Inc'},
                )
            ],
        )
        event = AuditEvent.objects.get(action=AuditActionChoices.ORGANIZATION_SUSPENDED)
        self.assertEqual(event.organization_id, self.organization.id)
        self.assertEqual(event.actor_type, AuditActorTypeChoices.PLATFORM)
        self.assertEqual(event.actor_user_id, self.staff.id)
        self.assertEqual(event.metadata, {'reason': 'Chargeback'})

    def test_suspend_requires_a_reason(self):
        for data in ({}, {'reason': '   '}, {'reason': 'x' * 501}):
            with self.subTest(data=data):
                response, apply_async = self.post('suspend', data)
                self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')
                apply_async.assert_not_called()
        self.organization.refresh_from_db()
        self.assertFalse(self.organization.is_suspended)

    def test_reactivate(self):
        self.post('suspend', {'reason': 'Chargeback'})

        response, apply_async = self.post('reactivate')

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['status'], OrganizationStatusChoices.ACTIVE)
        self.assertIsNone(response.data['suspension'])
        self.assertEqual(
            [email[0] for email in queued_emails(apply_async)],
            ['OrganizationReactivatedEmail'],
        )
        event = AuditEvent.objects.get(
            action=AuditActionChoices.ORGANIZATION_REACTIVATED
        )
        self.assertEqual(event.metadata, {})

    def test_invalid_transitions(self):
        response, _ = self.post('reactivate', {'reason': 'oops'})
        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['error']['code'], 'INVALID_STATE')
        self.assertEqual(
            response.data['error']['message'], 'This organization is already active.'
        )

        self.post('suspend', {'reason': 'Chargeback'})
        response, apply_async = self.post('suspend', {'reason': 'Again'})
        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
        self.assertEqual(
            response.data['error']['message'],
            'This organization is already suspended.',
        )
        apply_async.assert_not_called()
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditActionChoices.ORGANIZATION_SUSPENDED
            ).count(),
            1,
        )

    def test_unknown_organization_is_not_found(self):
        url = reverse('platform:organizations-suspend', args=[0])
        response = self.client.post(url, data={'reason': 'x'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_transfer_ownership(self):
        new_owner = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )

        response, apply_async = self.post(
            'transfer-ownership', {'member': new_owner.id, 'reason': 'Owner left'}
        )

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['owner']['id'], new_owner.user_id)
        self.organization.refresh_from_db()
        new_owner.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertEqual(self.organization.owner_id, new_owner.id)
        self.assertEqual(new_owner.role, MemberRoleChoices.OWNER)
        self.assertEqual(self.owner.role, MemberRoleChoices.ADMIN)
        self.assertTrue(self.owner.is_active)
        self.assertEqual(
            queued_emails(apply_async),
            [
                (
                    'OwnershipTransferredNewOwnerEmail',
                    [new_owner.user.email],
                    {'organization_name': 'Acme Inc'},
                ),
                (
                    'OwnershipTransferredPreviousOwnerEmail',
                    [self.owner.user.email],
                    {
                        'organization_name': 'Acme Inc',
                        'new_owner_name': new_owner.user.full_name,
                    },
                ),
            ],
        )
        event = AuditEvent.objects.get(
            action=AuditActionChoices.ORGANIZATION_OWNERSHIP_TRANSFERRED
        )
        self.assertEqual(event.metadata, {'reason': 'Owner left'})
        self.assertEqual(
            [change['field'] for change in event.changes],
            ['owner', 'previous_owner_role', 'new_owner_role'],
        )

    def test_transfer_invalid_targets(self):
        inactive = MemberFactory(organization=self.organization, is_active=False)
        other_organization_member = MemberFactory(organization=OrganizationFactory())
        for member in (inactive, other_organization_member, self.owner):
            with self.subTest(member=member.id):
                response, apply_async = self.post(
                    'transfer-ownership', {'member': member.id, 'reason': 'x'}
                )
                self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
                self.assertIn('member', response.data['error']['details'])
                apply_async.assert_not_called()
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.owner_id, self.owner.id)
        self.assertFalse(
            AuditEvent.objects.filter(
                action=AuditActionChoices.ORGANIZATION_OWNERSHIP_TRANSFERRED
            ).exists()
        )

    def test_transfer_requires_a_reason(self):
        new_owner = MemberFactory(organization=self.organization)
        response, _ = self.post('transfer-ownership', {'member': new_owner.id})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('reason', response.data['error']['details'])

    def test_failed_audit_rolls_back_and_sends_nothing(self):
        with mock.patch(
            'apps.platform.services.record_audit_event', side_effect=RuntimeError
        ):
            response, apply_async = self.post('suspend', {'reason': 'Chargeback'})
        self.assertEqual(
            response.status_code, http_status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        apply_async.assert_not_called()
        self.organization.refresh_from_db()
        self.assertFalse(self.organization.is_suspended)

    def test_transfer_changes_have_labels_in_the_audit_trail(self):
        new_owner = MemberFactory(organization=self.organization)
        self.post('transfer-ownership', {'member': new_owner.id, 'reason': 'x'})
        response = self.client.get(
            reverse('platform:audit_events-list'),
            {'action': AuditActionChoices.ORGANIZATION_OWNERSHIP_TRANSFERRED},
        )
        labels = [
            change['field_display'] for change in response.data['results'][0]['changes']
        ]
        self.assertEqual(labels, ['Owner', 'Previous owner role', 'New owner role'])
