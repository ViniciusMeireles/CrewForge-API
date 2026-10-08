from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status as http_status
from rest_framework.settings import api_settings
from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import DEFAULT_PASSWORD, UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.accounts.utils.email_verification import verification_url
from apps.accounts.utils.security_log import client_ip

USERNAME_FIELD = get_user_model().USERNAME_FIELD


class SecurityLogTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.user = UserFactory()

    def security_logs(self, method, *args, **kwargs):
        with self.assertLogs('security', level='INFO') as logs:
            response = method(*args, **kwargs)
        return response, logs

    def assert_event(self, logs, event, level='INFO', **fields):
        records = [r for r in logs.records if f'event={event}' in r.getMessage()]
        self.assertEqual(len(records), 1, logs.output)
        record = records[0]
        self.assertEqual(record.levelname, level)
        for key, value in fields.items():
            self.assertEqual(record.security_event[key], value)
        self.assertNotIn(self.user.email, record.getMessage())
        self.assertNotIn(DEFAULT_PASSWORD, record.getMessage())
        return record

    def login(self, password=DEFAULT_PASSWORD):
        return self.security_logs(
            self.client.post,
            reverse('accounts:token_obtain_pair'),
            {USERNAME_FIELD: getattr(self.user, USERNAME_FIELD), 'password': password},
            format='json',
        )

    def test_login_success_and_failure(self):
        response, logs = self.login()
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        record = self.assert_event(logs, 'auth.login.succeeded', user_id=self.user.pk)
        self.assertEqual(record.security_event['ip'], '127.0.0.1')
        self.assertNotIn(response.data['access'], record.getMessage())

        response, logs = self.login(password='wrong-password')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assert_event(logs, 'auth.login.failed', level='WARNING', user_id=None)

    @patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'auth': '1/min'})
    def test_throttled_auth_request(self):
        self.login()
        response, logs = self.login()
        self.assertEqual(response.status_code, http_status.HTTP_429_TOO_MANY_REQUESTS)
        self.assert_event(logs, 'auth.throttled', level='WARNING', scope='auth')

    def test_refresh_rejected(self):
        response, logs = self.security_logs(
            self.client.post,
            reverse('accounts:token_refresh'),
            {'refresh': 'not-a-token'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assert_event(logs, 'auth.refresh.rejected', level='WARNING')

    def test_logout(self):
        self.client.force_authenticate(user=self.user)
        response, logs = self.security_logs(
            self.client.post,
            reverse('accounts:logout'),
            {'refresh': str(RefreshToken.for_user(self.user))},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        self.assert_event(logs, 'auth.logout', user_id=self.user.pk)

    def test_password_reset_request(self):
        url = reverse('accounts:password_reset')
        with patch('apps.accounts.tasks.send_password_reset_email'):
            _, logs = self.security_logs(
                self.client.post, url, {'email': self.user.email}, format='json'
            )
            self.assert_event(
                logs, 'auth.password_reset.requested', user_id=self.user.pk
            )
            _, logs = self.security_logs(
                self.client.post, url, {'email': 'nobody@example.test'}, format='json'
            )
        record = self.assert_event(logs, 'auth.password_reset.requested', user_id=None)
        self.assertNotIn('nobody@example.test', record.getMessage())

    def test_password_reset_confirm_revokes_refresh_tokens(self):
        refresh = RefreshToken.for_user(self.user)
        payload = {
            'uid': urlsafe_base64_encode(force_bytes(self.user.pk)),
            'token': default_token_generator.make_token(self.user),
            'new_password': 'Newpass*123',
        }
        url = reverse('accounts:password_reset_confirm')
        response, logs = self.security_logs(
            self.client.post, url, payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assert_event(logs, 'auth.password_reset.completed', user_id=self.user.pk)
        self.assertTrue(
            BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists()
        )

        response, logs = self.security_logs(
            self.client.post, url, payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assert_event(logs, 'auth.password_reset.failed', level='WARNING')

    def test_email_verification(self):
        self.user.email_verified_at = None
        self.user.save(update_fields=['email_verified_at'])
        url = reverse('accounts:email_verify')
        params = dict(
            part.split('=', 1)
            for part in verification_url(self.user).split('?', 1)[1].split('&')
        )
        _, logs = self.security_logs(self.client.post, url, params, format='json')
        self.assert_event(logs, 'auth.email.verified', user_id=self.user.pk)
        _, logs = self.security_logs(self.client.post, url, params, format='json')
        self.assert_event(logs, 'auth.email_verification.failed', level='WARNING')

    def test_change_password(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('accounts:users-me-change-password')
        _, logs = self.security_logs(
            self.client.post,
            url,
            {'current_password': 'wrong-password', 'new_password': 'newPass*456'},
            format='json',
        )
        self.assert_event(
            logs, 'auth.password_change.failed', level='WARNING', user_id=self.user.pk
        )
        response, logs = self.security_logs(
            self.client.post,
            url,
            {'current_password': DEFAULT_PASSWORD, 'new_password': 'newPass*456'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assert_event(logs, 'auth.password.changed', user_id=self.user.pk)

    def test_organization_login(self):
        member = MemberFactory(user=self.user)
        self.client.force_authenticate(user=self.user)
        response, logs = self.security_logs(
            self.client.post,
            reverse('accounts:organizations-login', args=[member.organization_id]),
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assert_event(
            logs,
            'organization.login',
            user_id=self.user.pk,
            organization_id=member.organization_id,
        )

    def test_invitation_accepted(self):
        invitation = InvitationFactory(
            organization=OrganizationFactory(), email=self.user.email
        )
        self.client.force_authenticate(user=self.user)
        response, logs = self.security_logs(
            self.client.post,
            reverse(
                'accounts:invitations-accept',
                kwargs={'invitation_pk': invitation.pk},
            ),
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assert_event(
            logs,
            'invitation.accepted',
            user_id=self.user.pk,
            invitation_id=invitation.pk,
            organization_id=invitation.organization_id,
        )

    def test_signup(self):
        user = UserFactory.build()
        organization = OrganizationFactory.build()
        response, logs = self.security_logs(
            self.client.post,
            reverse('accounts:signup-list'),
            {
                'user': {
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'password': DEFAULT_PASSWORD,
                },
                'organization': {'name': organization.name, 'slug': organization.slug},
                'nickname': MemberFactory.build().nickname,
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        record = self.assert_event(
            logs, 'auth.signup', user_id=response.data['user']['id']
        )
        self.assertNotIn(user.email, record.getMessage())


class ClientIpTestCase(APITestCase):
    def ip_for(self, num_proxies):
        request = APIRequestFactory().get(
            '/', HTTP_X_FORWARDED_FOR='10.0.0.1, 203.0.113.9', REMOTE_ADDR='172.18.0.2'
        )
        with override_settings(
            REST_FRAMEWORK={**api_settings.user_settings, 'NUM_PROXIES': num_proxies}
        ):
            return client_ip(request)

    def test_uses_the_address_added_by_the_trusted_proxy(self):
        self.assertEqual(self.ip_for(1), '203.0.113.9')

    def test_without_proxies_uses_the_socket_address(self):
        self.assertEqual(self.ip_for(0), '172.18.0.2')
