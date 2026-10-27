from datetime import timedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.choices import MemberRoleChoices, OrganizationStatusChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.models.audit_event import AuditEvent
from apps.platform.choices import ImpersonationEndReasonChoices
from apps.platform.models import Impersonation

REASON = 'Checking why invitations do not show up.'


def signed_in(user) -> APIClient:
    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    client.refresh_token = str(refresh)
    return client


class ImpersonationTestCase(APITestCase):
    def setUp(self):
        self.staff = UserFactory(platform_role='support')
        self.organization = OrganizationFactory()
        self.member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.target = self.member.user
        self.staff_client = signed_in(self.staff)

    def start(self, target=None, client=None, reason=REASON):
        target = target or self.target
        return (client or self.staff_client).post(
            reverse('platform:users-impersonate', args=[target.id]),
            data={'reason': reason},
            format='json',
        )

    def enter_organization(self):
        return self.staff_client.post(
            reverse('accounts:organizations-login', args=[self.organization.id]),
            format='json',
        )

    def session(self):
        return self.staff_client.get(reverse('accounts:session'))

    def test_start_returns_the_session_as_the_user(self):
        response = self.start()

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['user']['id'], self.target.id)
        self.assertIsNone(response.data['organization'])
        impersonation = response.data['impersonation']
        self.assertEqual(impersonation['target']['id'], self.target.id)
        self.assertEqual(impersonation['staff']['id'], self.staff.id)
        record = Impersonation.objects.get()
        self.assertEqual(record.reason, REASON)
        self.assertEqual(record.expires_at - record.started_at, timedelta(minutes=30))
        session = self.session().data
        self.assertEqual(session['user']['id'], self.target.id)
        self.assertEqual(session['impersonation']['id'], record.id)
        event = AuditEvent.objects.get(
            action=AuditActionChoices.USER_IMPERSONATION_STARTED
        )
        self.assertEqual(event.subject_user_id, self.target.id)
        self.assertEqual(event.actor_user_id, self.staff.id)
        self.assertEqual(event.actor_type, AuditActorTypeChoices.PLATFORM)
        self.assertEqual(event.metadata, {'reason': REASON})

    def test_reason_is_required(self):
        response = self.start(reason='  ')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Impersonation.objects.exists())

    def test_role_none_cannot_impersonate(self):
        response = self.start(client=signed_in(UserFactory()))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_eligibility(self):
        targets = {
            'blocked': UserFactory(blocked=True),
            'deleted': UserFactory(is_active=False),
            'staff': UserFactory(platform_role='admin'),
            'self': self.staff,
        }
        for name, target in targets.items():
            with self.subTest(target=name):
                response = self.start(target=target)
                self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
                self.assertEqual(
                    response.data['error']['message'],
                    "This user can't be viewed (platform staff, blocked or deleted).",
                )
        self.assertFalse(Impersonation.objects.exists())

    def test_one_active_impersonation_per_staff(self):
        self.start()
        other_browser = signed_in(self.staff)
        response = self.start(target=UserFactory(), client=other_browser)
        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
        self.assertEqual(
            response.data['error']['message'],
            'You already have an active viewing session.',
        )

    def test_an_expired_leftover_does_not_block_a_new_one(self):
        self.start()
        Impersonation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        response = self.start(target=UserFactory(), client=signed_in(self.staff))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(Impersonation.objects.active().count(), 1)

    def test_sees_what_the_user_sees_and_cannot_write(self):
        self.start()
        self.assertEqual(self.enter_organization().status_code, http_status.HTTP_200_OK)
        members = self.staff_client.get(reverse('accounts:members-list'))
        self.assertEqual(members.status_code, http_status.HTTP_200_OK)

        other = MemberFactory(organization=self.organization)
        writes = [
            ('post', reverse('accounts:invitations-list'), {'email': 'x@acme.com'}),
            (
                'patch',
                reverse('accounts:members-update-role', args=[other.id]),
                {'role': 'manager'},
            ),
            ('post', reverse('teams:teams-list'), {'name': 'Ops'}),
            (
                'patch',
                reverse('accounts:organization_profiles-detail', args=[1]),
                {'description': 'x'},
            ),
            ('post', reverse('accounts:stored_files-list'), {}),
            ('patch', reverse('accounts:users-me'), {'first_name': 'Changed'}),
            ('post', reverse('platform:users-block', args=[other.user_id]), {}),
        ]
        for method, url, data in writes:
            with self.subTest(url=url):
                response = getattr(self.staff_client, method)(url, data, format='json')
                self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
                self.assertEqual(
                    response.data['error']['code'], 'READ_ONLY_IMPERSONATION'
                )
        self.target.refresh_from_db()
        self.assertNotEqual(self.target.first_name, 'Changed')

    def test_entering_an_organization_keeps_last_access_and_is_audited(self):
        before = self.member.last_login_at
        self.start()

        self.enter_organization()

        self.member.refresh_from_db()
        self.assertEqual(self.member.last_login_at, before)
        event = AuditEvent.objects.get(action=AuditActionChoices.ORGANIZATION_LOGIN)
        self.assertEqual(event.organization_id, self.organization.id)
        self.assertEqual(event.actor_user_id, self.target.id)
        self.assertEqual(event.impersonator_id, self.staff.id)

    def test_exit_returns_to_the_staff_account(self):
        self.start()
        self.enter_organization()

        response = self.staff_client.post(reverse('platform:impersonation-exit'))

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data, {'user': self.target.id})
        record = Impersonation.objects.get()
        self.assertEqual(record.end_reason, ImpersonationEndReasonChoices.EXIT)
        session = self.session().data
        self.assertEqual(session['user']['id'], self.staff.id)
        self.assertIsNone(session['impersonation'])
        event = AuditEvent.objects.get(
            action=AuditActionChoices.USER_IMPERSONATION_ENDED
        )
        self.assertEqual(event.subject_user_id, self.target.id)
        self.assertEqual(event.actor_user_id, self.staff.id)
        self.assertIsNone(event.impersonator_id)

    def test_exit_without_an_impersonation(self):
        response = self.staff_client.post(reverse('platform:impersonation-exit'))
        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)

    def test_expiry_ends_it_on_the_next_request(self):
        self.start()
        Impersonation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

        response = self.session()

        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['code'], 'IMPERSONATION_ENDED')
        self.assertEqual(
            response.data['error']['details'],
            {'reason': 'expired', 'user': self.target.id},
        )
        self.assertEqual(
            response.data['error']['message'], 'The viewing session ended.'
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditActionChoices.USER_IMPERSONATION_EXPIRED
            ).exists()
        )
        self.assertEqual(self.session().data['user']['id'], self.staff.id)

    def test_blocking_the_user_ends_it(self):
        self.start()
        admin = signed_in(UserFactory(platform_role='admin'))
        blocked = admin.post(
            reverse('platform:users-block', args=[self.target.id]),
            data={'reason': 'Abuse'},
            format='json',
        )
        self.assertEqual(blocked.status_code, http_status.HTTP_200_OK)

        response = self.session()

        self.assertEqual(response.data['error']['code'], 'IMPERSONATION_ENDED')
        self.assertEqual(response.data['error']['details']['reason'], 'user_blocked')
        self.assertEqual(
            response.data['error']['message'],
            'The user was blocked, so the viewing session ended.',
        )
        self.assertEqual(
            Impersonation.objects.get().end_reason,
            ImpersonationEndReasonChoices.USER_BLOCKED,
        )

    def test_suspended_organization_is_refused_but_the_impersonation_goes_on(self):
        self.start()
        self.organization.status = OrganizationStatusChoices.SUSPENDED
        self.organization.save(update_fields=['status'])

        response = self.enter_organization()

        self.assertEqual(response.data['error']['code'], 'ORGANIZATION_SUSPENDED')
        self.assertEqual(self.session().data['user']['id'], self.target.id)

    def test_sign_out_ends_it(self):
        self.start()
        response = self.staff_client.post(
            reverse('accounts:logout'),
            data={'refresh': self.staff_client.refresh_token},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            Impersonation.objects.get().end_reason,
            ImpersonationEndReasonChoices.SIGNED_OUT,
        )

    def test_the_user_sees_it_in_the_account_activity(self):
        self.start()
        self.staff_client.post(reverse('platform:impersonation-exit'))

        response = signed_in(self.target).get(reverse('accounts:users-me-activity'))

        actions = [event['action'] for event in response.data['results']]
        self.assertIn('user.impersonation_started', actions)
        self.assertIn('user.impersonation_ended', actions)
        started = next(
            event
            for event in response.data['results']
            if event['action'] == 'user.impersonation_started'
        )
        self.assertEqual(started['action_display'], 'Viewed by platform support')
        self.assertEqual(started['metadata'], {'reason': REASON})


class ImpersonationCookieTestCase(APITestCase):
    def test_browser_session_acts_as_the_user(self):
        staff = UserFactory(platform_role='support')
        target = UserFactory()
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get(reverse('accounts:session-config')).cookies['csrftoken'].value
        client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = str(
            RefreshToken.for_user(staff).access_token
        )

        started = client.post(
            reverse('platform:users-impersonate', args=[target.id]),
            data={'reason': REASON},
            format='json',
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(started.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            client.get(reverse('accounts:session')).data['user']['id'], target.id
        )
        refused = client.patch(
            reverse('accounts:users-me'),
            data={'first_name': 'x'},
            format='json',
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(refused.data['error']['code'], 'READ_ONLY_IMPERSONATION')
