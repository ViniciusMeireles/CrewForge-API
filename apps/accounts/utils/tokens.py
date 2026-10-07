from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)


def revoke_refresh_tokens(user) -> int:
    """Blacklist every outstanding refresh token of ``user``."""
    tokens = OutstandingToken.objects.filter(user=user).exclude(
        blacklistedtoken__isnull=False
    )
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in tokens],
        ignore_conflicts=True,
    )
    return len(tokens)
