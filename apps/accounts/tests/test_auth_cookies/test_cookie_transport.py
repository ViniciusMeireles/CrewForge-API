from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import DEFAULT_PASSWORD, UserFactory

USERNAME_FIELD = get_user_model().USERNAME_FIELD
ACCESS = 'access'
REFRESH = 'refresh'
COOKIE_HEADER = {'HTTP_X_AUTH_TRANSPORT': 'cookie'}
TOKEN_KEYS = {'access', 'refresh', 'auth_token'}


def token_keys_in(data) -> set[str]:
    if isinstance(data, dict):
        found = TOKEN_KEYS & set(data)
        for value in data.values():
            found |= token_keys_in(value)
        return found
    if isinstance(data, list):
        return set().union(*(token_keys_in(item) for item in data))
    return set()


class CookieTransportTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.organization = OrganizationFactory()
        self.member = self.organization.owner
        self.user = self.member.user
        self.client = APIClient(enforce_csrf_checks=True)
        response = self.client.get(reverse('accounts:session-config'))
        self.csrf = response.cookies['csrftoken'].value

    def credentials(self, user=None):
        user = user or self.user
        return {
            USERNAME_FIELD: getattr(user, USERNAME_FIELD),
            'password': DEFAULT_PASSWORD,
        }

    def post(self, url, data=None, csrf=True, cookie_mode=True):
        headers = {**COOKIE_HEADER} if cookie_mode else {}
        if csrf:
            headers['HTTP_X_CSRFTOKEN'] = self.csrf
        return self.client.post(url, data or {}, format='json', **headers)

    def login(self):
        response = self.post(reverse('accounts:token_obtain_pair'), self.credentials())
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        return response

    def assert_auth_cookie(self, response, name, path):
        cookie = response.cookies[name]
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], path)
        self.assertTrue(cookie.value)

    def assert_cleared(self, response, name):
        self.assertEqual(response.cookies[name].value, '')
        self.assertEqual(response.cookies[name]['max-age'], 0)


class CookieLoginTestCase(CookieTransportTestCase):
    def test_login_sets_http_only_cookies_and_hides_tokens(self):
        response = self.login()
        self.assert_auth_cookie(response, ACCESS, '/')
        self.assert_auth_cookie(response, REFRESH, '/api/auth/')
        self.assertEqual(token_keys_in(response.data), set())
        self.assertEqual(response.data['auth_user']['id'], self.user.id)

    def test_login_in_cookie_mode_requires_csrf(self):
        response = self.post(
            reverse('accounts:token_obtain_pair'), self.credentials(), csrf=False
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_login_without_cookie_header_keeps_tokens_in_body(self):
        response = APIClient().post(
            reverse('accounts:token_obtain_pair'), self.credentials(), format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertNotIn(ACCESS, response.cookies)

    @override_settings(
        AUTH_COOKIE_ACCESS_NAME='__Host-access',
        AUTH_COOKIE_REFRESH_NAME='__Secure-refresh',
        AUTH_COOKIE_SECURE=True,
    )
    def test_production_cookie_names_and_secure_flag(self):
        response = self.login()
        self.assertTrue(response.cookies['__Host-access']['secure'])
        self.assertTrue(response.cookies['__Secure-refresh']['secure'])

    @patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'auth': '2/min'})
    def test_login_is_throttled(self):
        url = reverse('accounts:token_obtain_pair')
        statuses = [self.post(url, self.credentials()).status_code for _ in range(3)]
        self.assertEqual(statuses[-1], http_status.HTTP_429_TOO_MANY_REQUESTS)


class CookieAuthenticationTestCase(CookieTransportTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.me_url = reverse('accounts:users-me')

    def test_cookie_authenticates_safe_requests_without_csrf(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.user.id)

    def test_cookie_authenticated_write_requires_csrf(self):
        response = self.client.patch(self.me_url, {'first_name': 'X'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

        response = self.client.patch(
            self.me_url,
            {'first_name': 'X'},
            format='json',
            HTTP_X_CSRFTOKEN=self.csrf,
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_bearer_write_does_not_need_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        access = str(RefreshToken.for_user(self.user).access_token)
        response = client.patch(
            self.me_url,
            {'first_name': 'Y'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {access}',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_invalid_access_cookie_is_treated_as_anonymous(self):
        self.client.cookies[ACCESS] = 'invalid'
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.login().status_code, http_status.HTTP_200_OK)


class CookieRefreshTestCase(CookieTransportTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.refresh_url = reverse('accounts:token_refresh')

    def test_refresh_from_cookie_rotates_without_body_tokens(self):
        old_refresh = self.client.cookies[REFRESH].value
        response = self.post(self.refresh_url, cookie_mode=False)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(token_keys_in(response.data), set())
        self.assert_auth_cookie(response, ACCESS, '/')
        self.assert_auth_cookie(response, REFRESH, '/api/auth/')
        self.assertNotEqual(response.cookies[REFRESH].value, old_refresh)
        jti = RefreshToken(old_refresh, verify=False)['jti']
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=jti).exists())

    def test_refresh_from_cookie_requires_csrf(self):
        response = self.post(self.refresh_url, csrf=False, cookie_mode=False)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_invalid_refresh_cookie_clears_cookies(self):
        self.client.cookies[REFRESH] = 'invalid'
        response = self.post(self.refresh_url, cookie_mode=False)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
        self.assert_cleared(response, ACCESS)
        self.assert_cleared(response, REFRESH)

    def test_body_refresh_keeps_tokens_in_body(self):
        refresh = str(RefreshToken.for_user(self.user))
        response = APIClient().post(
            self.refresh_url, {'refresh': refresh}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertNotIn(ACCESS, response.cookies)


class CookieLogoutTestCase(CookieTransportTestCase):
    def test_logout_blacklists_and_clears_cookies_and_session(self):
        self.login()
        self.post(reverse('accounts:organizations-login', args=[self.organization.id]))
        refresh = self.client.cookies[REFRESH].value

        response = self.post(reverse('accounts:logout'))
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        self.assert_cleared(response, ACCESS)
        self.assert_cleared(response, REFRESH)
        jti = RefreshToken(refresh, verify=False)['jti']
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=jti).exists())

        config = self.client.get(reverse('accounts:session-config'))
        self.assertFalse(config.data['session_configured'])

    def test_logout_without_refresh_in_cookie_mode_still_clears(self):
        response = self.post(reverse('accounts:logout'))
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        self.assert_cleared(response, ACCESS)

    def test_logout_in_cookie_mode_requires_csrf(self):
        self.login()
        response = self.post(reverse('accounts:logout'), csrf=False)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)


class CookieIssuersTestCase(CookieTransportTestCase):
    def user_payload(self):
        user = UserFactory.build()
        return {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'password': user.password,
        }

    def test_signup_sets_cookies_without_body_tokens(self):
        organization = OrganizationFactory.build()
        response = self.post(
            reverse('accounts:signup-list'),
            {
                'user': self.user_payload(),
                'organization': {
                    'name': organization.name,
                    'slug': organization.slug,
                },
                'nickname': MemberFactory.build().nickname,
            },
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(token_keys_in(response.data), set())
        self.assert_auth_cookie(response, ACCESS, '/')

    def test_signup_body_tokens_belong_to_the_new_user(self):
        MemberFactory.create_batch(3)
        organization = OrganizationFactory.build()
        response = APIClient().post(
            reverse('accounts:signup-list'),
            {
                'user': self.user_payload(),
                'organization': {
                    'name': organization.name,
                    'slug': organization.slug,
                },
                'nickname': MemberFactory.build().nickname,
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertNotEqual(response.data['id'], response.data['user']['id'])
        user_id = str(response.data['user']['id'])
        self.assertEqual(RefreshToken(response.data['refresh'])['user_id'], user_id)
        self.assertEqual(
            RefreshToken(response.data['user']['auth_token']['refresh'])['user_id'],
            user_id,
        )

    def test_create_with_invite_sets_cookies_without_body_tokens(self):
        user = self.user_payload()
        invitation = InvitationFactory(
            organization=self.organization, email=user['email'], expired_at=None
        )
        response = self.post(
            reverse('accounts:members-create-with-invite', args=[invitation.key]),
            {'user': user, 'nickname': MemberFactory.build().nickname},
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(token_keys_in(response.data), set())
        self.assert_auth_cookie(response, REFRESH, '/api/auth/')

    def test_accept_invitation_by_cookie_sets_cookies(self):
        self.login()
        invitation = InvitationFactory(
            organization=OrganizationFactory(), email=self.user.email
        )
        response = self.post(
            reverse(
                'accounts:invitations-accept', kwargs={'invitation_pk': invitation.pk}
            ),
            cookie_mode=False,
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(token_keys_in(response.data), set())
        self.assertIn('member_id', response.data)
        self.assert_auth_cookie(response, ACCESS, '/')

    def test_change_password_revokes_tokens_and_reissues_cookies(self):
        self.login()
        other_session = RefreshToken.for_user(self.user)
        response = self.client.post(
            reverse('accounts:users-me-change-password'),
            {'current_password': DEFAULT_PASSWORD, 'new_password': 'newPass*456'},
            format='json',
            HTTP_X_CSRFTOKEN=self.csrf,
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(
            BlacklistedToken.objects.filter(token__jti=other_session['jti']).exists()
        )
        self.assert_auth_cookie(response, REFRESH, '/api/auth/')
        new_refresh = response.cookies[REFRESH].value
        jti = RefreshToken(new_refresh, verify=False)['jti']
        self.assertFalse(BlacklistedToken.objects.filter(token__jti=jti).exists())


class OrganizationLoginSessionTestCase(CookieTransportTestCase):
    def test_organization_login_rotates_the_session_key(self):
        self.login()
        url = reverse('accounts:organizations-login', args=[self.organization.id])
        first = self.post(url).cookies['sessionid'].value
        second = self.post(url).cookies['sessionid'].value
        self.assertTrue(first)
        self.assertNotEqual(first, second)
