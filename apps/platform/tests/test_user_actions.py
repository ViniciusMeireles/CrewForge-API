from datetime import timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.factories.users import DEFAULT_PASSWORD, UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.audit.choices import AuditActionChoices
from apps.audit.models.audit_event import AuditEvent
from apps.platform.tests.mixins import PlatformTestMixin

APPLY_ASYNC = 'apps.accounts.tasks.send_email_task.apply_async'


class Device:
    """A signed-in client of ``user`` whose tokens were issued a minute ago."""

    def __init__(self, user):
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        issued_at = timezone.now() - timedelta(minutes=1)
        access.set_iat(at_time=issued_at)
        self.refresh = str(refresh)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def session(self):
        return self.client.get(reverse('accounts:session'))

    def refresh_tokens(self):
        return APIClient().post(
            reverse('accounts:token_refresh'),
            data={'refresh': self.refresh},
            format='json',
        )


def sign_in(user, password: str = DEFAULT_PASSWORD):
    return APIClient().post(
        reverse('accounts:token_obtain_pair'),
        data={'username': user.username, 'password': password},
        format='json',
    )


class PlatformUserActionTestCase(PlatformTestMixin, APITestCaseMixin, APITestCase):
    def setUp(self):
        self.target = UserFactory()
        self.staff = self.authenticate_staff('admin')

    def post(self, name: str, user=None, data=None):
        url = reverse(f'platform:users-{name}', args=[(user or self.target).id])
        with mock.patch(APPLY_ASYNC) as apply_async:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(url, data=data, format='json')
        return response, apply_async

    def test_block_refuses_next_request(self):
        laptop, phone = Device(self.target), Device(self.target)
        self.assertEqual(laptop.session().status_code, http_status.HTTP_200_OK)

        response, _ = self.post('block', data={'reason': 'Abuse report'})

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data['is_blocked'])
        self.assertEqual(response.data['blocking']['reason'], 'Abuse report')
        for device in (laptop, phone):
            response = device.session()
            self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(response.data['error']['code'], 'AUTHENTICATION_ERROR')
            refreshed = device.refresh_tokens()
            self.assertEqual(refreshed.status_code, http_status.HTTP_401_UNAUTHORIZED)
        response = sign_in(self.target)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['error']['code'], 'ACCOUNT_BLOCKED')

    def test_block_requires_a_reason(self):
        response, _ = self.post('block', data={'reason': ''})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_blocked)

    def test_block_keeps_memberships(self):
        from apps.accounts.factories.members import MemberFactory

        member = MemberFactory(user=self.target)
        self.post('block', data={'reason': 'Abuse report'})
        member.refresh_from_db()
        self.assertTrue(member.is_active)

    def test_unblock_does_not_restore_sessions(self):
        device = Device(self.target)
        self.post('block', data={'reason': 'Abuse report'})

        response, _ = self.post('unblock')

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['is_blocked'])
        self.assertEqual(device.session().data['error']['code'], 'AUTHENTICATION_ERROR')
        self.assertEqual(
            device.refresh_tokens().status_code, http_status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(sign_in(self.target).status_code, http_status.HTTP_200_OK)

    def test_self_block_refused_staff_block_allowed(self):
        response, _ = self.post('block', user=self.staff, data={'reason': 'x'})
        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
        self.assertEqual(
            response.data['error']['message'], "You can't block your own account."
        )

        other_staff = UserFactory(platform_role='support')
        response, _ = self.post('block', user=other_staff, data={'reason': 'x'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_invalid_block_transitions(self):
        response, _ = self.post('unblock')
        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['error']['message'], 'This user is not blocked.')

        self.post('block', data={'reason': 'x'})
        response, _ = self.post('block', data={'reason': 'again'})
        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
        self.assertEqual(
            response.data['error']['message'], 'This user is already blocked.'
        )

    def test_end_sessions(self):
        laptop, phone = Device(self.target), Device(self.target)

        response, _ = self.post('end-sessions')

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for device in (laptop, phone):
            self.assertEqual(
                device.session().status_code, http_status.HTTP_401_UNAUTHORIZED
            )
            self.assertEqual(
                device.refresh_tokens().status_code, http_status.HTTP_401_UNAUTHORIZED
            )
        self.assertEqual(sign_in(self.target).status_code, http_status.HTTP_200_OK)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_blocked)

    def test_resend_verification_and_cooldown(self):
        self.target.email_verified_at = None
        self.target.save(update_fields=['email_verified_at'])

        response, apply_async = self.post('resend-verification')

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        apply_async.assert_called_once()
        self.assertEqual(
            apply_async.call_args.kwargs['kwargs']['recipient_list'],
            [self.target.email],
        )

        response, apply_async = self.post('resend-verification')
        self.assertEqual(response.status_code, http_status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['error']['code'], 'THROTTLED')
        self.assertGreater(response.data['error']['details']['retry_after_seconds'], 0)
        apply_async.assert_not_called()

    def test_resend_verification_refused_when_verified(self):
        response, apply_async = self.post('resend-verification')
        self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['error']['code'], 'INVALID_STATE')
        apply_async.assert_not_called()

    def test_force_password_reset(self):
        device = Device(self.target)

        response, apply_async = self.post('force-password-reset', data={'reason': 'x'})

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.target.refresh_from_db()
        self.assertFalse(self.target.has_usable_password())
        self.assertEqual(
            device.session().status_code, http_status.HTTP_401_UNAUTHORIZED
        )
        self.assertEqual(
            sign_in(self.target).status_code, http_status.HTTP_401_UNAUTHORIZED
        )
        apply_async.assert_called_once()
        call = apply_async.call_args.kwargs['kwargs']
        self.assertTrue(call['email_class_path'].endswith('PasswordResetRequestEmail'))
        self.assertEqual(call['recipient_list'], [self.target.email])

    def test_account_events_land_in_the_target_activity(self):
        self.post('block', data={'reason': 'Abuse report'})
        event = AuditEvent.objects.get(action=AuditActionChoices.USER_BLOCKED)
        self.assertIsNone(event.organization_id)
        self.assertEqual(event.subject_user_id, self.target.id)
        self.assertEqual(event.actor_user_id, self.staff.id)

    def test_deleted_accounts_are_refused(self):
        deleted = UserFactory(is_active=False)
        for name in (
            'block',
            'unblock',
            'end-sessions',
            'resend-verification',
            'force-password-reset',
        ):
            with self.subTest(action=name):
                response, apply_async = self.post(
                    name, user=deleted, data={'reason': 'x'}
                )
                self.assertEqual(response.status_code, http_status.HTTP_409_CONFLICT)
                self.assertEqual(
                    response.data['error']['message'], 'This user account is deleted.'
                )
                apply_async.assert_not_called()
        self.assertFalse(AuditEvent.objects.filter(subject_user=deleted).exists())
