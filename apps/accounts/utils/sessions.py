from django.contrib.auth import get_user_model
from django.db.models import F
from django.utils import timezone

from apps.accounts.tokens import TOKEN_VERSION_CLAIM
from apps.accounts.utils.tokens import revoke_refresh_tokens


def revoke_sessions(user) -> None:
    """End every session of ``user``: bump the token version, blacklist refresh."""
    now = timezone.now()
    get_user_model().objects.filter(pk=user.pk).update(
        token_version=F('token_version') + 1,
        sessions_revoked_at=now,
        updated_at=now,
    )
    user.refresh_from_db(fields=['token_version', 'sessions_revoked_at', 'updated_at'])
    revoke_refresh_tokens(user)


def is_token_revoked(user, validated_token) -> bool:
    """Whether the token was issued for an older ``token_version`` of ``user``."""
    return validated_token.get(TOKEN_VERSION_CLAIM, 0) != user.token_version
