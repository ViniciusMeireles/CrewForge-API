from datetime import UTC, datetime
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.accounts.utils.sessions import is_token_revoked

REVOKED_AT = datetime(2026, 10, 23, 12, 0, 0, 900000, tzinfo=UTC)
REVOKED_SECOND = int(REVOKED_AT.timestamp())


class IsTokenRevokedTestCase(SimpleTestCase):
    def test_tokens_issued_before_the_revocation_second_are_revoked(self):
        user = SimpleNamespace(sessions_revoked_at=REVOKED_AT)
        self.assertTrue(is_token_revoked(user, REVOKED_SECOND - 1))

    def test_tokens_issued_in_the_revocation_second_are_kept(self):
        user = SimpleNamespace(sessions_revoked_at=REVOKED_AT)
        self.assertFalse(is_token_revoked(user, REVOKED_SECOND))

    def test_without_revocation_or_iat(self):
        self.assertFalse(
            is_token_revoked(SimpleNamespace(sessions_revoked_at=None), REVOKED_SECOND)
        )
        self.assertFalse(
            is_token_revoked(SimpleNamespace(sessions_revoked_at=REVOKED_AT), None)
        )
