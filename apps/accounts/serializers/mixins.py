from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.serializers import SerializerMetaclass

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.mixins.fields import OrganizationScopedFieldMixin
from apps.accounts.settings import api_settings

User = get_user_model()


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

    AUTO_SET_TOKEN = False

    refresh = serializers.SerializerMethodField()
    access = serializers.SerializerMethodField()

    class Meta:
        fields = ['refresh', 'access']

    def __init__(self, *args, auto_set_token: bool | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._refresh_token = {}
        self._access_token = {}
        self._auto_set_token = self.AUTO_SET_TOKEN
        if auto_set_token is not None:
            self._auto_set_token = auto_set_token

    def get_refresh(self, obj: User) -> str | None:
        """Return the refresh token."""
        if not obj or not obj.pk:
            return None
        if refresh := self._refresh_token.get(obj.pk):
            return refresh
        if not self._auto_set_token:
            return None
        self.set_tokens_for_user(obj)
        return self._refresh_token.get(obj.pk)

    def get_access(self, obj: User) -> str | None:
        """Return the access token."""
        if not obj or not obj.pk:
            return None
        if access := self._access_token.get(obj.pk):
            return access
        if not self._auto_set_token:
            return None
        self.set_tokens_for_user(user=obj)
        return self._access_token.get(obj.pk)

    def set_tokens_for_user(self, user: User):
        """Generate tokens directly from the user (no password required)."""
        refresh = import_string(api_settings.TOKEN_OBTAIN_SERIALIZER).get_token(
            user=user
        )
        self._refresh_token[user.pk] = str(refresh)
        self._access_token[user.pk] = str(refresh.access_token)
        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, user)
