def init_sentry(environ) -> bool:
    """Initialize Sentry when ``SENTRY_DSN`` is set; never send personal data."""
    if not (dsn := environ.get('SENTRY_DSN')):
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=environ.get('SENTRY_ENVIRONMENT') or None,
        release=environ.get('SENTRY_RELEASE') or None,
        data_collection={
            'user_info': False,
            'cookies': {'mode': 'off'},
            'http_headers': {'request': {'mode': 'off'}},
            'http_bodies': [],
            'url_query_params': {'mode': 'off'},
            'database_query_data': False,
        },
    )
    return True
