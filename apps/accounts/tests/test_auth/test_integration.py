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


class AuthIntegrationTestCase(APITestCaseMixin, APITestCase):
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

    def test_full_auth_flow(self):
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        obtain_response = self.client.post(self.token_url, data=payload, format='json')
        self.assertEqual(obtain_response.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', obtain_response.data)
        self.assertIn('refresh', obtain_response.data)
        access_token = obtain_response.data['access']
        refresh_token = obtain_response.data['refresh']

        verify_payload = {'token': access_token}
        verify_response = self.client.post(
            self.verify_url, data=verify_payload, format='json'
        )
        self.assertEqual(verify_response.status_code, http_status.HTTP_200_OK)

        refresh_payload = {'refresh': refresh_token}
        refresh_response = self.client.post(
            self.refresh_url, data=refresh_payload, format='json'
        )
        self.assertEqual(refresh_response.status_code, http_status.HTTP_200_OK)
        new_access = refresh_response.data['access']
        new_refresh = refresh_response.data['refresh']

        verify_new_payload = {'token': new_access}
        verify_new_response = self.client.post(
            self.verify_url, data=verify_new_payload, format='json'
        )
        self.assertEqual(verify_new_response.status_code, http_status.HTTP_200_OK)

        logout_response = self.client.post(
            self.logout_url, data={'refresh': new_refresh}, format='json'
        )
        self.assertEqual(logout_response.status_code, http_status.HTTP_204_NO_CONTENT)

        refresh_after_logout = self.client.post(
            self.refresh_url, data={'refresh': new_refresh}, format='json'
        )
        self.assertEqual(
            refresh_after_logout.status_code, http_status.HTTP_401_UNAUTHORIZED
        )

    def test_password_reset_full_flow(self):
        member = self.organization.owner
        user = member.user
        new_password = 'Newpass*123'

        reset_payload = {'email': user.email}
        reset_response = self.client.post(
            self.password_reset_url, data=reset_payload, format='json'
        )
        self.assertEqual(reset_response.status_code, http_status.HTTP_200_OK)
        self.assertIn('detail', reset_response.data)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        confirm_payload = {
            'uid': uid,
            'token': token,
            'new_password': new_password,
        }
        confirm_response = self.client.post(
            self.password_reset_confirm_url,
            data=confirm_payload,
            format='json',
        )
        self.assertEqual(confirm_response.status_code, http_status.HTTP_200_OK)
        self.assertIn('detail', confirm_response.data)

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

    def test_full_auth_flow_with_token_blacklist(self):
        member = self.organization.owner
        payload = {
            username_field: getattr(member.user, username_field),
            'password': DEFAULT_PASSWORD,
        }
        obtain = self.client.post(self.token_url, data=payload, format='json')
        self.assertEqual(obtain.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', obtain.data)
        self.assertIn('refresh', obtain.data)
        refresh_token = obtain.data['refresh']

        logout_resp = self.client.post(
            self.logout_url, data={'refresh': refresh_token}, format='json'
        )
        self.assertEqual(logout_resp.status_code, http_status.HTTP_204_NO_CONTENT)

        refresh_resp = self.client.post(
            self.refresh_url, data={'refresh': refresh_token}, format='json'
        )
        self.assertEqual(refresh_resp.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_password_reset_with_new_password_login(self):
        member = self.organization.owner
        user = member.user
        old_password = DEFAULT_PASSWORD
        new_password = 'Newpass*123'

        reset_resp = self.client.post(
            self.password_reset_url, data={'email': user.email}, format='json'
        )
        self.assertEqual(reset_resp.status_code, http_status.HTTP_200_OK)
        self.assertIn('detail', reset_resp.data)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        confirm_payload = {
            'uid': uid,
            'token': token,
            'new_password': new_password,
        }
        confirm_resp = self.client.post(
            self.password_reset_confirm_url,
            data=confirm_payload,
            format='json',
        )
        self.assertEqual(confirm_resp.status_code, http_status.HTTP_200_OK)
        self.assertIn('detail', confirm_resp.data)

        old_login_payload = {
            username_field: getattr(user, username_field),
            'password': old_password,
        }
        old_login_resp = self.client.post(
            self.token_url, data=old_login_payload, format='json'
        )
        self.assertEqual(old_login_resp.status_code, http_status.HTTP_401_UNAUTHORIZED)

        new_login_payload = {
            username_field: getattr(user, username_field),
            'password': new_password,
        }
        new_login_resp = self.client.post(
            self.token_url, data=new_login_payload, format='json'
        )
        self.assertEqual(new_login_resp.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', new_login_resp.data)
        self.assertIn('refresh', new_login_resp.data)
