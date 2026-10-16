from rest_framework.throttling import BaseThrottle


def client_ip(request) -> str | None:
    """Client address as resolved for throttling (respects ``NUM_PROXIES``)."""
    return BaseThrottle().get_ident(request)
