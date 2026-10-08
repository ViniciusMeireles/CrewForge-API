import logging

from rest_framework.throttling import BaseThrottle

logger = logging.getLogger('security')


def client_ip(request) -> str | None:
    """Client address as resolved for throttling (respects ``NUM_PROXIES``)."""
    return BaseThrottle().get_ident(request)


def log_security_event(
    event: str,
    request,
    user_id: int | None = None,
    level: int = logging.INFO,
    **fields,
) -> None:
    """Log an authentication event without credentials, tokens or emails."""
    if user_id is None and (user := getattr(request, 'user', None)):
        user_id = user.pk if user.is_authenticated else None
    data = {'event': event, 'user_id': user_id, 'ip': client_ip(request), **fields}
    message = ' '.join(
        f'{key}={value}' for key, value in data.items() if value is not None
    )
    logger.log(level, message, extra={'security_event': data})
