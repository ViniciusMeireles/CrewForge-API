from apps.accounts.authentication import JWTCookieAuthentication
from apps.platform.impersonation import (
    refuse_writes_while_impersonating,
    resolve_impersonation,
)


class ImpersonationAuthentication(JWTCookieAuthentication):
    def authenticate(self, request):
        if (result := super().authenticate(request)) is None:
            return None
        staff, token = result
        if (impersonation := resolve_impersonation(request, staff)) is None:
            return result
        refuse_writes_while_impersonating(request)
        request._request.impersonator = staff
        request._request.impersonation = impersonation
        return impersonation.target, token
