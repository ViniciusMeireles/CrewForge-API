from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status as http_status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.factories.users import DEFAULT_PASSWORD
from apps.accounts.tests.mixins import APITestCaseMixin

username_field = get_user_model().USERNAME_FIELD


class AuthCRUDTestCase(APITestCaseMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.token_url = reverse(viewname='accounts:token_obtain_pair')
        cls.refresh_url = reverse(viewname='accounts:token_refresh')
        cls.verify_url = reverse(viewname='accounts:token_verify')
        cls.logout_url = reverse(viewname='accounts:logout')
        cls.password_reset_url = reverse(viewname='accounts:password_reset')
        cls.password_reset_confirm_url = reverse(
            viewname='accounts:password_reset_confirm'
        )
        cls.email_preview_url_list = [
            reverse(viewname='accounts:password_reset_email_preview'),
        ]

    def setUp(self):
        self.organization = self.new_account()

    def _get_tokens(self):
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        response = self.client.post(self.token_url, data=payload, format='json')
        return response.data

    def test_token_obtain_pair_success(self):
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        response = self.client.post(self.token_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_token_obtain_pair_invalid_credentials(self):
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': 'invalid_password',
        }
        response = self.client.post(self.token_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('access', response.data)
        self.assertNotIn('refresh', response.data)

    def test_token_refresh_success(self):
        tokens = self._get_tokens()
        refresh_payload = {'refresh': tokens['refresh']}
        refresh_response = self.client.post(
            self.refresh_url, data=refresh_payload, format='json'
        )
        self.assertEqual(refresh_response.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', refresh_response.data)
        self.assertIn('refresh', refresh_response.data)

    def test_token_refresh_invalid(self):
        payload = {'refresh': 'invalid_token'}
        response = self.client.post(self.refresh_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_token_verify_success(self):
        tokens = self._get_tokens()
        verify_payload = {'token': tokens['access']}
        verify_response = self.client.post(
            self.verify_url, data=verify_payload, format='json'
        )
        self.assertEqual(verify_response.status_code, http_status.HTTP_200_OK)

    def test_token_verify_invalid(self):
        payload = {'token': 'invalid_token'}
        response = self.client.post(self.verify_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_password_reset_request_success(self):
        member = self.organization.owner
        payload = {'email': member.user.email}
        response = self.client.post(
            self.password_reset_url, data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('detail', response.data)

    def test_password_reset_request_invalid_email(self):
        payload = {'email': 'invalid@invalid.com'}
        response = self.client.post(
            self.password_reset_url, data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)

    def test_password_reset_confirm_success(self):
        member = self.organization.owner
        user = member.user
        new_password = 'Newpass*123'
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_confirm_payload = {
            'uid': uid,
            'token': token,
            'new_password': new_password,
        }
        reset_confirm_response = self.client.post(
            self.password_reset_confirm_url,
            data=reset_confirm_payload,
            format='json',
        )
        self.assertEqual(reset_confirm_response.status_code, http_status.HTTP_200_OK)
        self.assertIn('detail', reset_confirm_response.data)
        login_payload = {
            username_field: getattr(user, username_field),
            'password': new_password,
        }
        login_response = self.client.post(
            self.token_url, data=login_payload, format='json'
        )
        self.assertEqual(login_response.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', login_response.data)
        self.assertIn('refresh', login_response.data)

    def test_password_reset_confirm_invalid_token(self):
        member = self.organization.owner
        user = member.user
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_confirm_payload = {
            'uid': uid,
            'token': 'invalid-token',
            'new_password': 'Newpass*123',
        }
        reset_confirm_response = self.client.post(
            self.password_reset_confirm_url,
            data=reset_confirm_payload,
            format='json',
        )
        self.assertEqual(
            reset_confirm_response.status_code, http_status.HTTP_400_BAD_REQUEST
        )
        self.assertIn('non_field_errors', reset_confirm_response.data)

    def test_password_reset_confirm_invalid_uid(self):
        member = self.organization.owner
        user = member.user
        token = default_token_generator.make_token(user)
        reset_confirm_payload = {
            'uid': 'invalid-uid',
            'token': token,
            'new_password': 'Newpass*123',
        }
        reset_confirm_response = self.client.post(
            self.password_reset_confirm_url,
            data=reset_confirm_payload,
            format='json',
        )
        self.assertEqual(
            reset_confirm_response.status_code, http_status.HTTP_400_BAD_REQUEST
        )
        self.assertIn('non_field_errors', reset_confirm_response.data)

    def test_password_reset_confirm_empty_password(self):
        member = self.organization.owner
        user = member.user
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_confirm_payload = {
            'uid': uid,
            'token': token,
            'new_password': '',
        }
        reset_confirm_response = self.client.post(
            self.password_reset_confirm_url,
            data=reset_confirm_payload,
            format='json',
        )
        self.assertEqual(
            reset_confirm_response.status_code, http_status.HTTP_400_BAD_REQUEST
        )
        self.assertIn('new_password', reset_confirm_response.data)

    def test_email_preview(self):
        for url in self.email_preview_url_list:
            response = self.client.get(url)
            self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_logout_success(self):
        tokens = self._get_tokens()
        response = self.client.post(
            self.logout_url, data={'refresh': tokens['refresh']}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_logout_invalid_token(self):
        response = self.client.post(
            self.logout_url, data={'refresh': 'invalid_token'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)

    def test_logout_already_blacklisted(self):
        tokens = self._get_tokens()
        self.client.post(
            self.logout_url, data={'refresh': tokens['refresh']}, format='json'
        )
        response = self.client.post(
            self.logout_url, data={'refresh': tokens['refresh']}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)

    def test_logout_no_refresh_token(self):
        response = self.client.post(self.logout_url, data={}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)

    def test_logout_clears_session(self):
        tokens = self._get_tokens()
        session = self.client.session
        self.assertIsNotNone(session.get('organization_id'))
        self.client.post(
            self.logout_url, data={'refresh': tokens['refresh']}, format='json'
        )
        session = self.client.session
        self.assertIsNone(session.get('organization_id'))

    def test_logout_token_cannot_refresh_after(self):
        tokens = self._get_tokens()
        self.client.post(
            self.logout_url, data={'refresh': tokens['refresh']}, format='json'
        )
        response = self.client.post(
            self.refresh_url, data={'refresh': tokens['refresh']}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_token_obtain_pair_missing_username(self):
        payload = {'password': DEFAULT_PASSWORD}
        response = self.client.post(self.token_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_token_obtain_pair_missing_password(self):
        member = self.organization.owner
        payload = {username_field: getattr(member.user, username_field)}
        response = self.client.post(self.token_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_token_obtain_pair_inactive_user(self):
        member = self.organization.owner
        user = member.user
        user.is_active = False
        user.save()
        payload = {
            username_field: getattr(user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        response = self.client.post(self.token_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_expired_token(self):
        member = self.organization.owner
        user = member.user
        past_time = datetime.now(tz=timezone.utc) - timedelta(days=365)
        with patch(
            'rest_framework_simplejwt.tokens.aware_utcnow',
            return_value=past_time,
        ):
            token = RefreshToken.for_user(user)
            expired_refresh = str(token)
        payload = {'refresh': expired_refresh}
        response = self.client.post(self.refresh_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_password_reset_confirm_weak_password(self):
        member = self.organization.owner
        user = member.user
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_confirm_payload = {
            'uid': uid,
            'token': token,
            'new_password': 'short',
        }
        response = self.client.post(
            self.password_reset_confirm_url,
            data=reset_confirm_payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)

    def test_logout_with_expired_refresh_token(self):
        member = self.organization.owner
        user = member.user
        past_time = datetime.now(tz=timezone.utc) - timedelta(days=365)
        with patch(
            'rest_framework_simplejwt.tokens.aware_utcnow',
            return_value=past_time,
        ):
            token = RefreshToken.for_user(user)
            expired_refresh = str(token)
        response = self.client.post(
            self.logout_url, data={'refresh': expired_refresh}, format='json'
        )
        self.assertIn(
            response.status_code,
            [http_status.HTTP_204_NO_CONTENT, http_status.HTTP_400_BAD_REQUEST],
        )

    def test_email_preview_all_endpoints(self):
        email_preview_urls = [
            reverse(viewname='accounts:password_reset_email_preview'),
            reverse(viewname='accounts:invitation_email_preview'),
        ]
        for url in email_preview_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, http_status.HTTP_200_OK)
