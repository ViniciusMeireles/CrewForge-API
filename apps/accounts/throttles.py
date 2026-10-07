from rest_framework.settings import api_settings
from rest_framework.throttling import ScopedRateThrottle


class AuthThrottleMixin:
    throttle_scope = 'auth'
    throttle_classes = [*api_settings.DEFAULT_THROTTLE_CLASSES, ScopedRateThrottle]


class AuthRefreshThrottleMixin(AuthThrottleMixin):
    throttle_scope = 'auth_refresh'
