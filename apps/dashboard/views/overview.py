from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.mixins.requests import OrganizationScopedRequestMixin
from apps.accounts.permissions.generics import IsActiveMember
from apps.dashboard.selectors import build_overview
from apps.dashboard.serializers.overview import OverviewSerializer


@extend_schema(
    tags=[_('Dashboard')],
    summary=_('Get organization overview'),
    description=_(
        'Organization overview for the current member. '
        'Sections the member cannot access are null.',
    ),
    responses={200: OverviewSerializer},
)
class OverviewView(OrganizationScopedRequestMixin, APIView):
    permission_classes = [IsActiveMember]
    http_method_names = ['get', 'options']

    def get(self, request, *args, **kwargs):
        data = build_overview(
            member=self.auth_member,
            user=self.auth_user,
            now=timezone.now(),
        )
        serializer = OverviewSerializer(
            instance=data,
            context={'request': request},
        )
        return Response(data=serializer.data, status=status.HTTP_200_OK)
