from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import (
    InvitationErrorMessages,
    MemberRoleChoices,
    OrganizationStatusChoices,
)
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationSuspensionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.owner = self.organization.owner
        self.client.force_authenticate(member=self.owner)

    def suspend(self):
        self.organization.status = OrganizationStatusChoices.SUSPENDED
        self.organization.save(update_fields=['status'])

    def test_context_refused_on_the_next_request_and_dropped(self):
        members_url = reverse('accounts:members-list')
        self.assertEqual(
            self.client.get(members_url).status_code, http_status.HTTP_200_OK
        )

        self.suspend()
        response = self.client.get(members_url)

        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['code'], 'ORGANIZATION_SUSPENDED')
        self.assertNotIn('organization_id', self.client.session)

    def test_every_organization_area_is_refused(self):
        self.suspend()
        for url in (
            reverse('dashboard:overview'),
            reverse('accounts:invitations-list'),
            reverse('teams:teams-list'),
        ):
            with self.subTest(url=url):
                self.client.force_authenticate(
                    member=self.owner, organization_auth=False
                )
                session = self.client.session
                session['organization_id'] = self.organization.id
                session.save()
                response = self.client.get(url)
                self.assertEqual(
                    response.data['error']['code'], 'ORGANIZATION_SUSPENDED'
                )

    def test_login_refused(self):
        self.suspend()
        url = reverse('accounts:organizations-login', args=[self.organization.id])
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['code'], 'ORGANIZATION_SUSPENDED')

    def test_selection_lists_it_as_suspended_without_context(self):
        self.suspend()
        response = self.client.get(reverse('accounts:session'))

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsNone(response.data['organization'])
        statuses = {
            item['id']: item['status'] for item in response.data['organizations']
        }
        self.assertEqual(statuses[self.organization.id], 'suspended')
        self.assertNotIn('organization_id', self.client.session)

    def test_new_invitations_cannot_be_created(self):
        self.suspend()
        response = self.client.post(
            reverse('accounts:invitations-list'),
            data={'email': 'new@example.com', 'role': MemberRoleChoices.MEMBER},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['code'], 'ORGANIZATION_SUSPENDED')

    def test_pending_invitations_cannot_be_accepted(self):
        user = UserFactory()
        invitation = InvitationFactory(organization=self.organization, email=user.email)
        self.suspend()
        self.client.force_authenticate(user=user)

        response = self.client.post(
            reverse(
                'accounts:invitations-accept', kwargs={'invitation_pk': invitation.pk}
            ),
            format='json',
        )

        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['error']['code'], 'INVALID_STATE')
        self.assertEqual(
            response.data['error']['message'],
            InvitationErrorMessages.ORGANIZATION_SUSPENDED.label,
        )
        invitation.refresh_from_db()
        self.assertFalse(invitation.is_accepted)

    def test_received_invitations_stay_readable(self):
        self.suspend()
        response = self.client.get(reverse('accounts:invitations-received'))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_reactivation_restores_access(self):
        self.suspend()
        self.organization.status = OrganizationStatusChoices.ACTIVE
        self.organization.save(update_fields=['status'])
        url = reverse('accounts:organizations-login', args=[self.organization.id])
        self.assertEqual(
            self.client.post(url, format='json').status_code, http_status.HTTP_200_OK
        )
        self.assertEqual(
            self.client.get(reverse('accounts:members-list')).status_code,
            http_status.HTTP_200_OK,
        )

    def test_other_organizations_are_unaffected(self):
        other = OrganizationFactory()
        self.suspend()
        self.client.force_authenticate(member=other.owner)
        response = self.client.get(reverse('accounts:members-list'))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
