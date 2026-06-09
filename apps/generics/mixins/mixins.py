from django.contrib.auth import get_user_model
from django.utils.functional import cached_property

User = get_user_model()


class RequestUserMixin:
    """Mixin for views to add user, member, and organization properties."""

    @cached_property
    def auth_user(self) -> User | None:
        """Get the user from the context."""
        if (user := self.request.user) and user.is_authenticated:
            return user
        return None
