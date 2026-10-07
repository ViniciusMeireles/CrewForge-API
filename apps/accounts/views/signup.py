from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from apps.accounts.models.member import Member
from apps.accounts.serializers.signup import SignupSerializer
from apps.accounts.throttles import AuthThrottleMixin
from apps.accounts.utils.auth_cookies import (
    enforce_csrf,
    move_auth_token_to_cookies,
    wants_cookie_transport,
)


@extend_schema_view(
    create=extend_schema(
        tags=[str(_('Signup'))], description=_('Create a new account.')
    ),
)
class SignupViewSet(
    AuthThrottleMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = SignupSerializer
    queryset = Member.objects.all()
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        if wants_cookie_transport(request):
            enforce_csrf(request)
        response = super().create(request, *args, **kwargs)
        return move_auth_token_to_cookies(request, response, response.data.get('user'))
