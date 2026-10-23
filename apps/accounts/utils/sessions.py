from django.utils import timezone

from apps.accounts.utils.tokens import revoke_refresh_tokens


def revoke_sessions(user) -> None:
    """End every session of ``user``: older access tokens, refresh tokens."""
    user.sessions_revoked_at = timezone.now()
    user.save(update_fields=['sessions_revoked_at', 'updated_at'])
    revoke_refresh_tokens(user)


def is_token_revoked(user, issued_at: int | None) -> bool:
    """Whether a token issued at ``issued_at`` (epoch seconds) predates a revocation."""
    revoked_at = user.sessions_revoked_at
    if revoked_at is None or issued_at is None:
        return False
    return issued_at < int(revoked_at.timestamp())
