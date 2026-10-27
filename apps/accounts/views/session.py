from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.mixins.requests import OrganizationScopedRequestMixin
from apps.accounts.serializers.session import SessionSerializer
from apps.accounts.utils.requests import clear_suspended_organization_context


@extend_schema(
    tags=[_('Sessions')],
    summary=_('Get session'),
    description=_(
        'Return the authenticated user, their active organizations and the '
        'organization and member of the current session.'
    ),
    responses={200: SessionSerializer},
)
class SessionView(OrganizationScopedRequestMixin, APIView):
    permission_classes = [IsAuthenticated]

    def refuse_suspended_organization_context(self, request) -> None:
        clear_suspended_organization_context(request)

    def get(self, request, *args, **kwargs):
        user = self.auth_user
        organization = member.organization if (member := self.auth_member) else None
        data = {
            'user': user,
            'organizations': user.active_organizations.select_related('profile'),
            'organization': organization,
            'member': member,
            'impersonation': getattr(request, 'impersonation', None),
        }

        serializer = SessionSerializer(
            instance=data,
            context={'request': request},
        )
        return Response(data=serializer.data, status=status.HTTP_200_OK)
