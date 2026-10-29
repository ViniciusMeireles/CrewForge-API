import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.factories.users import DEFAULT_PASSWORD, UserFactory
from apps.accounts.tokens import VERSION_CLAIM, VersionedRefreshToken
from apps.accounts.utils.sessions import revoke_sessions


def _bearer(token) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


class TokenVersionTestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.me_url = reverse('accounts:users-me')

    def test_issued_tokens_carry_the_user_version(self):
        refresh = VersionedRefreshToken.for_user(self.user)
        self.assertEqual(refresh[VERSION_CLAIM], 0)
        self.assertEqual(refresh.access_token[VERSION_CLAIM], 0)

    def test_revocation_in_the_same_second_refuses_older_tokens(self):
        access = VersionedRefreshToken.for_user(self.user).access_token
        revoke_sessions(self.user)
        response = _bearer(access).get(self.me_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_tokens_issued_after_revocation_work(self):
        revoke_sessions(self.user)
        access = VersionedRefreshToken.for_user(self.user).access_token
        response = _bearer(access).get(self.me_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_token_without_version_counts_as_zero(self):
        access = AccessToken.for_user(self.user)
        self.assertEqual(
            _bearer(access).get(self.me_url).status_code, http_status.HTTP_200_OK
        )
        revoke_sessions(self.user)
        self.assertEqual(
            _bearer(access).get(self.me_url).status_code,
            http_status.HTTP_401_UNAUTHORIZED,
        )

    def test_revoke_sessions_bumps_the_version(self):
        revoke_sessions(self.user)
        revoke_sessions(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.token_version, 2)
        self.assertIsNotNone(self.user.sessions_revoked_at)

    def test_login_and_refresh_keep_the_version(self):
        revoke_sessions(self.user)
        response = APIClient().post(
            reverse('accounts:token_obtain_pair'),
            {'username': self.user.username, 'password': DEFAULT_PASSWORD},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        refresh = response.data['refresh']
        response = APIClient().post(
            reverse('accounts:token_refresh'), {'refresh': refresh}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(AccessToken(response.data['access'])[VERSION_CLAIM], 1)


class TokenIssuingPathsTestCase(SimpleTestCase):
    def test_tokens_are_only_minted_by_the_versioned_class(self):
        offenders = []
        for path in Path(settings.BASE_DIR, 'apps').rglob('*.py'):
            if 'tests' in path.parts or path.name == 'tokens.py':
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and node.attr == 'for_user'
                    and isinstance(node.value, ast.Name)
                    and node.value.id in {'RefreshToken', 'AccessToken'}
                ):
                    offenders.append(f'{path}:{node.lineno}')
        self.assertEqual(offenders, [])
