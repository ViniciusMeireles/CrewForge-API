from django.contrib.auth import get_user_model
from django.utils.functional import cached_property

from apps.generics.utils.serializers import get_user_of_context

User = get_user_model()


class AuthUserFieldMixin:
    @cached_property
    def auth_user(self) -> User | None:
        """Get the user from the context."""
        return get_user_of_context(self.context)
