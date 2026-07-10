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


class AuthSerializerTestCase(APITestCaseMixin, APITestCase):
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

    def test_token_obtain_pair_response_fields(self):
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        response = self.client.post(self.token_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_token_refresh_response_fields(self):
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        response = self.client.post(self.token_url, data=payload, format='json')
        refresh_token = response.data.get('refresh')
        refresh_payload = {'refresh': refresh_token}
        refresh_response = self.client.post(
            self.refresh_url, data=refresh_payload, format='json'
        )
        self.assertEqual(refresh_response.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', refresh_response.data)
        self.assertIn('refresh', refresh_response.data)

    def test_token_verify_no_response_body(self):
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        response = self.client.post(self.token_url, data=payload, format='json')
        access_token = response.data.get('access')
        verify_payload = {'token': access_token}
        verify_response = self.client.post(
            self.verify_url, data=verify_payload, format='json'
        )
        self.assertEqual(verify_response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(verify_response.data), 0)

    def test_password_reset_response_fields(self):
        member = self.organization.owner
        payload = {'email': member.user.email}
        response = self.client.post(
            self.password_reset_url, data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('detail', response.data)

    def test_password_reset_confirm_response_fields(self):
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

    def test_validate_empty_password_reset(self):
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

    def test_validate_invalid_token_password_reset(self):
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

    def test_validate_invalid_uid_password_reset(self):
        user = self.organization.owner.user
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

    def test_validate_nonexistent_email_password_reset(self):
        payload = {'email': 'nonexistent@example.com'}
        response = self.client.post(
            self.password_reset_url, data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)

    def test_token_obtain_pair_serializer_fields(self):
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        response = self.client.post(self.token_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(set(response.data.keys()), {'access', 'refresh', 'auth_user'})

    def test_password_reset_serializer_fields(self):
        member = self.organization.owner
        payload = {'email': member.user.email}
        response = self.client.post(
            self.password_reset_url, data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(set(response.data.keys()), {'detail'})

    def test_password_reset_confirm_serializer_fields(self):
        member = self.organization.owner
        user = member.user
        new_password = 'Newpass*123'
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token_value = default_token_generator.make_token(user)
        payload = {
            'uid': uid,
            'token': token_value,
            'new_password': new_password,
        }
        response = self.client.post(
            self.password_reset_confirm_url, data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(set(response.data.keys()), {'detail'})

    def test_logout_serializer_fields(self):
        tokens = self._get_tokens()
        response = self.client.post(
            self.logout_url, data={'refresh': tokens['refresh']}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        self.assertIsNone(response.data)

    def test_validate_empty_email_password_reset(self):
        payload = {'email': ''}
        response = self.client.post(
            self.password_reset_url, data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_validate_nonexistent_user_password_reset(self):
        existing_user = self.organization.owner.user
        nonexistent_pk = 99999
        fake_uid = urlsafe_base64_encode(force_bytes(nonexistent_pk))
        token = default_token_generator.make_token(existing_user)
        payload = {
            'uid': fake_uid,
            'token': token,
            'new_password': 'Newpass*123',
        }
        response = self.client.post(
            self.password_reset_confirm_url, data=payload, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)
