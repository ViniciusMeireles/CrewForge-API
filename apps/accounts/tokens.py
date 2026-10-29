from rest_framework_simplejwt.tokens import RefreshToken

TOKEN_VERSION_CLAIM = 'tv'


class VersionedRefreshToken(RefreshToken):
    """Refresh token carrying ``User.token_version``; its access token inherits it."""

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token[TOKEN_VERSION_CLAIM] = user.token_version
        return token
