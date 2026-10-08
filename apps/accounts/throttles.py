import logging

from rest_framework.settings import api_settings
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.utils.security_log import log_security_event


class AuthThrottleMixin:
    throttle_scope = 'auth'
    throttle_classes = [*api_settings.DEFAULT_THROTTLE_CLASSES, ScopedRateThrottle]

    def throttled(self, request, wait):
        log_security_event(
            'auth.throttled', request, level=logging.WARNING, scope=self.throttle_scope
        )
        super().throttled(request, wait)


class AuthRefreshThrottleMixin(AuthThrottleMixin):
    throttle_scope = 'auth_refresh'
