from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices, StoredFileAccess
from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import DEFAULT_PASSWORD, UserFactory
from apps.audit.choices import AuditActionChoices
from apps.audit.tests.mixins import AuditAPITestCaseMixin


class AuditRecordingTestMixin(AuditAPITestCaseMixin):
    def assert_single(self, action, **fields):
        events = list(self.events(action))
        self.assertEqual(len(events), 1, [e.action for e in self.events()])
        event = events[0]
        for key, value in fields.items():
            self.assertEqual(getattr(event, key), value, key)
        return event

    def changed(self, event) -> dict:
        return {c['field']: (c['before'], c['after']) for c in event.changes}


class OrganizationRecordingTestCase(AuditRecordingTestMixin, APITestCase):
    def test_organization_created(self):
        self.client.force_authenticate(user=UserFactory())
        self.clear_events()
        data = OrganizationFactory.build()
        response = self.client.post(
            reverse('accounts:organizations-list'),
            {'name': data.name, 'slug': data.slug},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        event = self.assert_single(
            AuditActionChoices.ORGANIZATION_CREATED,
            organization_id=response.data['id'],
        )
        self.assertEqual(event.actor_member.organization_id, response.data['id'])
        self.assertEqual(self.changed(event)['name'], (None, data.name))

    def test_organization_updated(self):
        response = self.client.patch(
            reverse('accounts:organizations-detail', args=[self.organization.pk]),
            {'name': 'Renamed'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        event = self.assert_single(
            AuditActionChoices.ORGANIZATION_UPDATED,
            organization_id=self.organization.pk,
            actor_member=self.owner,
        )
        self.assertEqual(
            self.changed(event)['name'], (self.organization.name, 'Renamed')
        )

    def test_noop_update_records_nothing(self):
        self.client.patch(
            reverse('accounts:organizations-detail', args=[self.organization.pk]),
            {'name': self.organization.name},
            format='json',
        )
        self.assertFalse(self.events(AuditActionChoices.ORGANIZATION_UPDATED).exists())

    def test_organization_login(self):
        self.client.force_authenticate(member=self.owner)
        self.assert_single(
            AuditActionChoices.ORGANIZATION_LOGIN,
            organization_id=self.organization.pk,
            actor_member=self.owner,
        )

    def test_profile_updated(self):
        profile = self.organization.get_profile()
        response = self.client.put(
            reverse('accounts:organization_profiles-detail', args=[profile.pk]),
            {'website': 'https://updated.example', 'description': 'New'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        event = self.assert_single(
            AuditActionChoices.ORGANIZATION_PROFILE_UPDATED,
            organization_id=self.organization.pk,
        )
        self.assertEqual(self.changed(event)['website'][1], 'https://updated.example')


class MemberRecordingTestCase(AuditRecordingTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.member = MemberFactory(organization=self.organization)

    def test_member_updated(self):
        response = self.client.patch(
            reverse('accounts:members-detail', args=[self.member.pk]),
            {'nickname': 'new-nick'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        event = self.assert_single(AuditActionChoices.MEMBER_UPDATED)
        self.assertEqual(
            self.changed(event)['nickname'], (self.member.nickname, 'new-nick')
        )

    def test_member_role_changed(self):
        self.client.patch(
            reverse('accounts:members-update-role', args=[self.member.pk]),
            {'role': MemberRoleChoices.ADMIN},
            format='json',
        )
        event = self.assert_single(
            AuditActionChoices.MEMBER_ROLE_CHANGED, target_id=str(self.member.pk)
        )
        self.assertEqual(self.changed(event), {'role': ('member', 'admin')})
        self.assertFalse(self.events(AuditActionChoices.MEMBER_UPDATED).exists())

    def test_member_removed(self):
        response = self.client.delete(
            reverse('accounts:members-detail', args=[self.member.pk])
        )
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        event = self.assert_single(
            AuditActionChoices.MEMBER_REMOVED, target_label=self.member.audit_label
        )
        self.assertEqual(event.changes, [])

    def test_failed_update_records_nothing(self):
        response = self.client.patch(
            reverse('accounts:members-update-role', args=[self.member.pk]),
            {'role': 'emperor'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertFalse(self.events().exists())

    def test_member_joined_with_invite(self):
        invitation = InvitationFactory(
            organization=self.organization, email='invitee@example.test'
        )
        self.client.logout()
        user = UserFactory.build()
        response = self.client.post(
            reverse('accounts:members-create-with-invite', args=[invitation.key]),
            {
                'user': {
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'password': DEFAULT_PASSWORD,
                },
                'nickname': 'invitee',
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        joined = self.assert_single(
            AuditActionChoices.MEMBER_JOINED, organization_id=self.organization.pk
        )
        self.assertEqual(joined.actor_user_id, response.data['user']['id'])
        self.assertEqual(str(joined.actor_member_id), joined.target_id)
        signup = self.assert_single(AuditActionChoices.AUTH_SIGNUP)
        self.assertIsNone(signup.organization_id)
        self.assertEqual(signup.subject_user_id, response.data['user']['id'])


class InvitationRecordingTestCase(AuditRecordingTestMixin, APITestCase):
    def test_invitation_created_stores_email_not_key(self):
        data = InvitationFactory.build()
        response = self.client.post(
            reverse('accounts:invitations-list'),
            {'email': data.email, 'role': data.role, 'expired_at': data.expired_at},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        event = self.assert_single(AuditActionChoices.INVITATION_CREATED)
        changes = self.changed(event)
        self.assertEqual(changes['email'], (None, data.email))
        self.assertNotIn('key', changes)
        self.assertEqual(event.target_label, data.email)

    def test_invitation_updated_and_deleted(self):
        invitation = InvitationFactory(organization=self.organization)
        response = self.client.put(
            reverse('accounts:invitations-detail', args=[invitation.pk]),
            {
                'email': invitation.email,
                'role': MemberRoleChoices.ADMIN,
                'expired_at': invitation.expired_at,
                'organization': self.organization.pk,
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        event = self.assert_single(AuditActionChoices.INVITATION_UPDATED)
        self.assertEqual(self.changed(event), {'role': ('member', 'admin')})
        self.client.delete(reverse('accounts:invitations-detail', args=[invitation.pk]))
        self.assert_single(AuditActionChoices.INVITATION_DELETED)

    @override_settings(FRONTEND_URL='http://example.com')
    def test_invitation_email_sent(self):
        invitation = InvitationFactory(organization=self.organization)
        url = reverse('accounts:invitations-send-email', args=[invitation.pk])
        self.assertEqual(self.client.post(url).status_code, http_status.HTTP_200_OK)
        self.assert_single(
            AuditActionChoices.INVITATION_EMAIL_SENT, target_id=str(invitation.pk)
        )
        self.assertEqual(
            self.client.post(url).status_code, http_status.HTTP_429_TOO_MANY_REQUESTS
        )
        self.assertEqual(
            self.events(AuditActionChoices.INVITATION_EMAIL_SENT).count(), 1
        )

    def accept_as(self, user, invitation):
        self.client.logout()
        self.client.force_authenticate(user=user)
        return self.client.post(
            reverse(
                'accounts:invitations-accept', kwargs={'invitation_pk': invitation.pk}
            ),
            format='json',
        )

    def test_invitation_accepted_by_a_new_member(self):
        user = UserFactory()
        invitation = InvitationFactory(organization=self.organization, email=user.email)
        response = self.accept_as(user, invitation)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        accepted = self.assert_single(
            AuditActionChoices.INVITATION_ACCEPTED, organization_id=self.organization.pk
        )
        joined = self.assert_single(AuditActionChoices.MEMBER_JOINED)
        self.assertEqual(accepted.actor_member_id, response.data['member_id'])
        self.assertEqual(joined.target_id, str(response.data['member_id']))
        self.assertFalse(self.events(AuditActionChoices.MEMBER_READMITTED).exists())

    def test_invitation_accepted_by_a_former_member(self):
        former = MemberFactory(organization=self.organization, is_active=False)
        invitation = InvitationFactory(
            organization=self.organization, email=former.user.email
        )
        response = self.accept_as(former.user, invitation)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assert_single(AuditActionChoices.INVITATION_ACCEPTED)
        self.assert_single(
            AuditActionChoices.MEMBER_READMITTED, target_id=str(former.pk)
        )
        self.assertFalse(self.events(AuditActionChoices.MEMBER_JOINED).exists())

    def test_session_member_of_another_organization_is_not_the_actor(self):
        user = UserFactory()
        other = MemberFactory(user=user)
        invitation = InvitationFactory(organization=self.organization, email=user.email)
        self.client.logout()
        self.client.force_authenticate(member=other)
        self.clear_events()
        self.client.post(
            reverse(
                'accounts:invitations-accept', kwargs={'invitation_pk': invitation.pk}
            ),
            format='json',
        )
        event = self.assert_single(AuditActionChoices.INVITATION_ACCEPTED)
        self.assertEqual(event.organization_id, self.organization.pk)
        self.assertNotEqual(event.actor_member_id, other.pk)

    def test_invitation_declined(self):
        user = UserFactory()
        invitation = InvitationFactory(organization=self.organization, email=user.email)
        self.client.logout()
        self.client.force_authenticate(user=user)
        response = self.client.post(
            reverse(
                'accounts:invitations-decline', kwargs={'invitation_pk': invitation.pk}
            ),
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assert_single(
            AuditActionChoices.INVITATION_DECLINED,
            organization_id=self.organization.pk,
            actor_user=user,
        )


class StoredFileRecordingTestCase(AuditRecordingTestMixin, APITestCase):
    def test_stored_file_lifecycle(self):
        response = self.client.post(
            reverse('accounts:stored_files-list'),
            {
                'file': SimpleUploadedFile(
                    'a.txt', b'hello', content_type='text/plain'
                ),
                'name': 'My File',
                'viewing_permission': StoredFileAccess.OWNER.value,
                'updating_permission': StoredFileAccess.OWNER.value,
                'owner': self.owner.user_id,
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        uploaded = self.assert_single(AuditActionChoices.STORED_FILE_UPLOADED)
        self.assertEqual(self.changed(uploaded)['name'], (None, 'My File'))
        detail = reverse('accounts:stored_files-detail', args=[response.data['uuid']])
        self.client.patch(detail, {'name': 'Renamed'}, format='multipart')
        updated = self.assert_single(AuditActionChoices.STORED_FILE_UPDATED)
        self.assertEqual(self.changed(updated)['name'], ('My File', 'Renamed'))
        self.client.delete(detail)
        self.assert_single(
            AuditActionChoices.STORED_FILE_DELETED, target_id=uploaded.target_id
        )

    def test_unaudited_file_from_factory_keeps_working(self):
        StoredFileFactory()
        self.assertFalse(self.events().exists())


class ProfileRecordingTestCase(AuditRecordingTestMixin, APITestCase):
    url = 'accounts:users-me'

    def test_profile_updated(self):
        response = self.client.patch(
            reverse(self.url), {'first_name': 'Changed'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        event = self.assert_single(
            AuditActionChoices.USER_PROFILE_UPDATED, organization_id=None
        )
        self.assertEqual(self.changed(event)['first_name'][1], 'Changed')
        self.assertEqual(event.subject_user, self.owner.user)

    def test_email_change_is_recorded_without_values(self):
        self.client.patch(
            reverse(self.url), {'email': 'new@example.test'}, format='json'
        )
        event = self.assert_single(AuditActionChoices.USER_PROFILE_UPDATED)
        self.assertEqual(self.changed(event)['email'], (None, None))
        self.assertEqual(event.metadata, {'email_changed': True})
        self.assertNotIn('new@example.test', str(event.changes))

    def test_noop_records_nothing(self):
        self.client.patch(
            reverse(self.url), {'first_name': self.owner.user.first_name}, format='json'
        )
        self.assertFalse(self.events().exists())

    def test_password_is_never_stored(self):
        self.client.patch(reverse(self.url), {'first_name': 'X'}, format='json')
        for event in self.events():
            self.assertNotIn('password', self.changed(event))
