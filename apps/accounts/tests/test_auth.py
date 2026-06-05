from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.users import DEFAULT_PASSWORD
from apps.accounts.tests.mixins import APITestCaseMixin

username_field = get_user_model().USERNAME_FIELD


class AuthAPITestCase(APITestCaseMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.token_url = reverse(viewname='accounts:token_obtain_pair')
        cls.refresh_url = reverse(viewname='accounts:token_refresh')
        cls.verify_url = reverse(viewname='accounts:token_verify')
        cls.password_reset_url = reverse(viewname='accounts:password_reset')
        cls.password_reset_confirm_url = reverse(
            viewname='accounts:password_reset_confirm'
        )
        cls.email_preview_url_list = [
            reverse(viewname='accounts:password_reset_email_preview'),
        ]

    def setUp(self):
        self.organization = self.new_account()

    def test_token_obtain_pair(self):
        """Test the token obtain pair view."""
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        response = self.client.post(
            path=self.token_url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_token_obtain_pair_invalid_credentials(self):
        """Test the token obtain pair view with invalid credentials."""
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': 'invalid_password',
        }
        response = self.client.post(
            path=self.token_url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('access', response.data)
        self.assertNotIn('refresh', response.data)

    def test_token_refresh(self):
        """Test the token refresh view."""
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        response = self.client.post(
            path=self.token_url,
            data=payload,
            format='json',
        )
        refresh_token = response.data.get('refresh')
        refresh_payload = {
            'refresh': refresh_token,
        }
        refresh_response = self.client.post(
            path=self.refresh_url,
            data=refresh_payload,
            format='json',
        )
        self.assertEqual(refresh_response.status_code, http_status.HTTP_200_OK)
        self.assertIn('refresh', refresh_response.data)

    def test_token_refresh_invalid(self):
        """Test the token refresh view with an invalid token."""
        payload = {
            'refresh': 'invalid_token',
        }
        response = self.client.post(
            path=self.refresh_url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_token_verify(self):
        """Test the token verify view."""
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        response = self.client.post(
            path=self.token_url,
            data=payload,
            format='json',
        )
        access_token = response.data.get('access')
        verify_payload = {
            'token': access_token,
        }
        verify_response = self.client.post(
            path=self.verify_url,
            data=verify_payload,
            format='json',
        )
        self.assertEqual(verify_response.status_code, http_status.HTTP_200_OK)

    def test_token_verify_invalid(self):
        """Test the token verify view with an invalid token."""
        payload = {
            'token': 'invalid_token',
        }
        response = self.client.post(
            path=self.verify_url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_password_reset(self):
        """Test the password reset request view."""
        member = self.organization.owner
        payload = {
            'email': member.user.email,
        }
        response = self.client.post(
            path=self.password_reset_url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('detail', response.data)

    def test_password_reset_invalid_email(self):
        """Test the password reset request view with an invalid email."""
        payload = {
            'email': 'invalid@invalid.com',
        }
        response = self.client.post(
            path=self.password_reset_url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)

    def test_password_reset_confirm(self):
        """Test the password reset confirm view."""
        member = self.organization.owner
        user = member.user
        new_password = 'Newpass*123'
        # First, request a password reset to get the uid and token
        reset_request_payload = {
            'email': user.email,
        }
        reset_request_response = self.client.post(
            path=self.password_reset_url,
            data=reset_request_payload,
            format='json',
        )
        self.assertEqual(reset_request_response.status_code, http_status.HTTP_200_OK)
        # In a real scenario, the uid and token would be sent via email.
        # Here, we simulate this by generating them directly.
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        reset_confirm_payload = {
            'uid': uid,
            'token': token,
            'new_password': new_password,
        }
        reset_confirm_response = self.client.post(
            path=self.password_reset_confirm_url,
            data=reset_confirm_payload,
            format='json',
        )
        self.assertEqual(reset_confirm_response.status_code, http_status.HTTP_200_OK)
        self.assertIn('detail', reset_confirm_response.data)
        # Verify that the user can log in with the new password
        login_payload = {
            username_field: getattr(user, username_field),
            'password': new_password,
        }
        login_response = self.client.post(
            path=self.token_url,
            data=login_payload,
            format='json',
        )
        self.assertEqual(login_response.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', login_response.data)
        self.assertIn('refresh', login_response.data)

    def test_password_reset_confirm_invalid_token(self):
        """Test the password reset confirm view with an invalid token."""
        member = self.organization.owner
        user = member.user
        new_password = 'Newpass*123'
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        invalid_token = 'invalid-token'

        reset_confirm_payload = {
            'uid': uid,
            'token': invalid_token,
            'new_password': new_password,
        }
        reset_confirm_response = self.client.post(
            path=self.password_reset_confirm_url,
            data=reset_confirm_payload,
            format='json',
        )
        self.assertEqual(
            reset_confirm_response.status_code, http_status.HTTP_400_BAD_REQUEST
        )
        self.assertIn('non_field_errors', reset_confirm_response.data)

    def test_password_reset_confirm_invalid_uid(self):
        """Test the password reset confirm view with an invalid uid."""
        new_password = 'Newpass*123'
        invalid_uid = 'invalid-uid'
        member = self.organization.owner
        user = member.user
        token = default_token_generator.make_token(user)

        reset_confirm_payload = {
            'uid': invalid_uid,
            'token': token,
            'new_password': new_password,
        }
        reset_confirm_response = self.client.post(
            path=self.password_reset_confirm_url,
            data=reset_confirm_payload,
            format='json',
        )
        self.assertEqual(
            reset_confirm_response.status_code, http_status.HTTP_400_BAD_REQUEST
        )
        self.assertIn('non_field_errors', reset_confirm_response.data)

    def test_password_reset_empty_password(self):
        """Test the password reset confirm view with an empty new password."""
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
            path=self.password_reset_confirm_url,
            data=reset_confirm_payload,
            format='json',
        )
        self.assertEqual(
            reset_confirm_response.status_code, http_status.HTTP_400_BAD_REQUEST
        )
        self.assertIn('new_password', reset_confirm_response.data)

    def test_email_rendered(self):
        for url in self.email_preview_url_list:
            response = self.client.get(url)
            self.assertEqual(response.status_code, http_status.HTTP_200_OK)
