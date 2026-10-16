from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status as http_status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.factories.users import DEFAULT_PASSWORD, UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.audit.choices import AuditActorTypeChoices
from apps.audit.models.audit_event import AuditEvent

USERNAME_FIELD = get_user_model().USERNAME_FIELD
NEW_PASSWORD = f'{DEFAULT_PASSWORD}!'
WRONG_PASSWORD = f'wrong-{DEFAULT_PASSWORD}'


class SecurityEventPersistenceTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.user = UserFactory()

    def stored(self, action):
        return list(AuditEvent.objects.filter(action=action))

    def login(self, password=DEFAULT_PASSWORD, username=None):
        return self.client.post(
            reverse('accounts:token_obtain_pair'),
            {
                USERNAME_FIELD: username or getattr(self.user, USERNAME_FIELD),
                'password': password,
            },
            format='json',
        )

    def test_login_succeeded_is_an_account_event(self):
        self.login()
        (event,) = self.stored('auth.login.succeeded')
        self.assertIsNone(event.organization_id)
        self.assertEqual(event.subject_user, self.user)
        self.assertEqual(event.ip, '127.0.0.1')

    def test_failed_login_is_stored_for_the_targeted_account(self):
        response = self.login(password=WRONG_PASSWORD)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        (event,) = self.stored('auth.login.failed')
        self.assertEqual(event.subject_user, self.user)
        self.assertIsNone(event.actor_user)
        self.assertEqual(event.actor_type, AuditActorTypeChoices.USER)
        self.assertNotIn(self.user.email, str(event.metadata))

    def test_failed_login_for_an_unknown_account(self):
        self.login(username='nobody-here')
        (event,) = self.stored('auth.login.failed')
        self.assertIsNone(event.subject_user)

    @patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'auth': '1/min'})
    def test_throttled_is_not_stored(self):
        self.login()
        self.login()
        self.assertEqual(self.stored('auth.throttled'), [])

    def test_refresh_rejected_is_not_stored(self):
        self.client.post(
            reverse('accounts:token_refresh'), {'refresh': 'bad'}, format='json'
        )
        self.assertEqual(self.stored('auth.refresh.rejected'), [])

    def test_logout(self):
        self.client.post(
            reverse('accounts:logout'),
            {'refresh': str(RefreshToken.for_user(self.user))},
            format='json',
        )
        (event,) = self.stored('auth.logout')
        self.assertEqual(event.subject_user, self.user)

    def test_password_change_and_failure(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('accounts:users-me-change-password')
        self.client.post(
            url,
            {'current_password': WRONG_PASSWORD, 'new_password': NEW_PASSWORD},
            format='json',
        )
        self.client.post(
            url,
            {'current_password': DEFAULT_PASSWORD, 'new_password': NEW_PASSWORD},
            format='json',
        )
        self.assertEqual(len(self.stored('auth.password_change.failed')), 1)
        (event,) = self.stored('auth.password.changed')
        self.assertNotIn(NEW_PASSWORD, str(event.metadata) + str(event.changes))

    def test_password_reset_flow(self):
        with patch('apps.accounts.tasks.send_password_reset_email'):
            self.client.post(
                reverse('accounts:password_reset'),
                {'email': self.user.email},
                format='json',
            )
        payload = {
            'uid': urlsafe_base64_encode(force_bytes(self.user.pk)),
            'token': default_token_generator.make_token(self.user),
            'new_password': NEW_PASSWORD,
        }
        url = reverse('accounts:password_reset_confirm')
        self.client.post(url, payload, format='json')
        self.client.post(url, payload, format='json')
        (requested,) = self.stored('auth.password_reset.requested')
        self.assertNotIn(self.user.email, str(requested.metadata))
        self.assertEqual(len(self.stored('auth.password_reset.completed')), 1)
        self.assertEqual(len(self.stored('auth.password_reset.failed')), 1)

    def test_signup(self):
        user = UserFactory.build()
        response = self.client.post(
            reverse('accounts:signup-list'),
            {
                'user': {
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'password': DEFAULT_PASSWORD,
                },
                'organization': {'name': 'Signup Org', 'slug': 'signup-org'},
                'nickname': 'founder',
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        (event,) = self.stored('auth.signup')
        self.assertEqual(event.subject_user_id, response.data['user']['id'])
        self.assertNotIn(user.email, str(event.metadata))
