from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from apps.accounts.models.member import Member
from apps.accounts.serializers.signup import SignupSerializer


@extend_schema_view(
    create=extend_schema(
        tags=[str(_('Signup'))], description=_('Create a new account.')
    ),
)
class SignupViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = SignupSerializer
    queryset = Member.objects.all()
    permission_classes = [AllowAny]
