def init_sentry(environ) -> bool:
    """Initialize Sentry when ``SENTRY_DSN`` is set; never send personal data."""
    if not (dsn := environ.get('SENTRY_DSN')):
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=environ.get('SENTRY_ENVIRONMENT') or None,
        release=environ.get('SENTRY_RELEASE') or None,
        send_default_pii=False,
    )
    return True
