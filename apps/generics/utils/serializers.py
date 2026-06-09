from django.contrib.auth import get_user_model

User = get_user_model()


def get_user_of_context(context: dict) -> User | None:
    """
    Get the user from the context.
    """
    request = context.get('request')
    if not request:
        return None
    elif not (user := request.user):
        return None
    elif not user.is_authenticated:
        return None
    if not user.is_active:
        return None
    return user
