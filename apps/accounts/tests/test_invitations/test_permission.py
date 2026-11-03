from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import InvitationEmailErrorMessages, MemberRoleChoices
from apps.accounts.factories.invitations import InvitationFactory
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


def _invitation_url(role=MemberRoleChoices.MEMBER, name='accounts:invitations-detail'):
    return lambda case: reverse(
        name, args=[InvitationFactory(organization=case.organization, role=role).pk]
    )


def _payload(role=MemberRoleChoices.MEMBER):
    def build(case):
        data = InvitationFactory.build()
        return {'email': data.email, 'role': role, 'expired_at': data.expired_at}

    return build


LIST = reverse('accounts:invitations-list')
SEND_EMAIL = 'accounts:invitations-send-email'
FORM_CREATE = reverse('accounts:invitations-form-options-create')
FORM_UPDATE = reverse('accounts:invitations-form-options-update')


class InvitationPermissionMatrixTestCase(
    PermissionMatrixMixin, APITestCaseMixin, APITestCase
):
    actions = {
        'list': Action('get', lambda case: LIST),
        'create': Action('post', lambda case: LIST, _payload()),
        'retrieve': Action('get', _invitation_url()),
        'update': Action('put', _invitation_url(), _payload(MemberRoleChoices.ADMIN)),
        'delete': Action('delete', _invitation_url()),
        'send_email': Action('post', _invitation_url(name=SEND_EMAIL)),
        'retrieve_owner_invite': Action(
            'get', _invitation_url(MemberRoleChoices.OWNER)
        ),
        'retrieve_admin_invite': Action(
            'get', _invitation_url(MemberRoleChoices.ADMIN)
        ),
        'retrieve_manager_invite': Action(
            'get', _invitation_url(MemberRoleChoices.MANAGER)
        ),
        'form_options_create': Action('get', lambda case: FORM_CREATE),
        'form_options_update': Action('get', lambda case: FORM_UPDATE),
    }
    matrix = {
        ANONYMOUS: {
            'list': 401,
            'retrieve': 401,
            'create': 401,
            'update': 401,
            'delete': 401,
            'send_email': 401,
            'form_options_create': 401,
            'form_options_update': 401,
        },
        NO_SESSION: {'form_options_create': 403, 'form_options_update': 403},
        INACTIVE: {
            'list': 403,
            'retrieve': 403,
            'create': 403,
            'update': 403,
            'delete': 403,
            'send_email': 403,
            'form_options_create': 403,
            'form_options_update': 403,
        },
        MEMBER: {
            'create': 403,
            'update': 403,
            'delete': 403,
            'send_email': 403,
            'form_options_create': 403,
            'form_options_update': 403,
        },
        MANAGER: {'form_options_create': 403, 'form_options_update': 403},
        ADMIN: {
            'retrieve_admin_invite': 404,
            'retrieve_manager_invite': 200,
            'retrieve': 200,
            'form_options_create': 200,
            'form_options_update': 200,
        },
        OWNER: {
            'retrieve_owner_invite': 200,
            'retrieve_admin_invite': 200,
            'form_options_create': 200,
            'form_options_update': 200,
        },
        OTHER_ORGANIZATION: {
            'retrieve': 404,
            'update': 404,
            'delete': 404,
            'send_email': 404,
        },
    }

    def setUp(self):
        self.organization = OrganizationFactory()


class InvitationPermissionTestCase(APITestCaseMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.detail_url_name = 'accounts:invitations-detail'
        cls.list_url = reverse('accounts:invitations-list')
        cls.send_email_url_name = 'accounts:invitations-send-email'

    def setUp(self):
        self.organization = self.new_account()

    def _detail_url(self, invitation):
        return reverse(self.detail_url_name, args=[invitation.pk])

    def _send_email_url(self, invitation):
        return reverse(self.send_email_url_name, args=[invitation.pk])

    def _create_invitation(self, **kwargs):
        return InvitationFactory(organization=self.organization, **kwargs)

    def _invitation_payload(self, **overrides):
        data = InvitationFactory.build()
        payload = {
            'email': data.email,
            'role': data.role,
            'expired_at': data.expired_at,
        }
        payload.update(overrides)
        return payload

    # --- Admin role ---

    def test_admin_can_create_manager_invite(self):
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        payload = self._invitation_payload(role=MemberRoleChoices.MANAGER)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_admin_can_create_member_invite(self):
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        payload = self._invitation_payload(role=MemberRoleChoices.MEMBER)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_admin_cannot_create_admin_invite(self):
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        payload = self._invitation_payload(role=MemberRoleChoices.ADMIN)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_admin_cannot_create_owner_invite(self):
        admin = MemberFactory(
            organization=self.organization,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=admin)
        payload = self._invitation_payload(role=MemberRoleChoices.OWNER)
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    # --- Send email edge cases ---

    @override_settings(FRONTEND_URL='http://example.com')
    def test_send_email_cooldown_returns_429(self):
        invitation = self._create_invitation(
            expired_at=timezone.now() + timedelta(days=7),
            last_email_sent_at=timezone.now(),
        )
        url = self._send_email_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(
            response.data['code'],
            InvitationEmailErrorMessages.COOLDOWN_ACTIVE.value,
        )
        self.assertIn('retry_after_seconds', response.data)

    @override_settings(FRONTEND_URL='http://example.com')
    def test_send_email_expired_returns_400(self):
        invitation = self._create_invitation(
            is_expired=True,
            expired_at=timezone.now() - timedelta(days=1),
        )
        url = self._send_email_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    @override_settings(FRONTEND_URL='http://example.com')
    def test_send_email_accepted_returns_400(self):
        invitation = self._create_invitation(
            is_accepted=True,
            expired_at=timezone.now() + timedelta(days=7),
        )
        url = self._send_email_url(invitation)
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
