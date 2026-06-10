from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.serializers import SerializerMetaclass
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.mixins.fields import OrganizationScopedFieldMixin
from apps.accounts.settings import api_settings


class ValidateRoleSerializerMixin(OrganizationScopedFieldMixin):
    """
    Mixin to validate the role of a user.
    """

    def validate_role(self, value):
        """Validate that the role is one of the allowed roles."""
        if self.instance == self.auth_member:
            raise serializers.ValidationError(_('Not allowed to change your own role.'))
        if (
            value == MemberRoleChoices.OWNER
            and not self.auth_member.has_owner_permission
        ) or (
            value == MemberRoleChoices.ADMIN
            and not self.auth_member.has_admin_permission
        ):
            raise serializers.ValidationError(
                _('Not allowed to set the %(role)s role.') % {'role': value}
            )
        return value


class UserTokenSerializerMixin(metaclass=SerializerMetaclass):
    """
    Mixin to add access and refresh token fields to a serializer.
    """

    refresh = serializers.SerializerMethodField()
    access = serializers.SerializerMethodField()

    username_field = get_user_model().USERNAME_FIELD

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._refresh_token = None
        self._access_token = None

    def get_refresh(self, obj) -> str | None:
        """Return the refresh token."""
        return self._refresh_token

    def get_access(self, obj) -> str | None:
        """Return the access token."""
        return self._access_token

    def set_tokens_for_user(self, user):
        """Generate tokens directly from the user (no password required)."""
        refresh = RefreshToken.for_user(user)
        self._refresh_token = str(refresh)
        self._access_token = str(refresh.access_token)
        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, user)
