def str_to_bool(value: str | None) -> bool:
    """Convert a string to a boolean value."""
    if not value:
        return False
    return str(value).lower() in ('yes', 'true', 't', '1', 'y', 'on')
