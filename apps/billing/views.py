from typing import cast

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.mixins.requests import OrganizationScopedRequestMixin
from apps.billing import selectors
from apps.billing.models.plan import Plan
from apps.billing.models.subscription import Subscription
from apps.billing.permissions import BillingPermission
from apps.billing.serializers import PlanSerializer, SubscriptionDetailSerializer
from apps.generics.errors import InvalidState

BILLING_TAGS = [cast(str, _('Billing'))]


@extend_schema(
    tags=BILLING_TAGS,
    summary=_('List plans'),
    description=_('The active plans offered for self-service, with their limits.'),
    responses={200: PlanSerializer(many=True)},
)
class PlanListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        plans = Plan.objects.offered()
        return Response(PlanSerializer(plans, many=True).data)


@extend_schema(
    tags=BILLING_TAGS,
    summary=_('Get subscription'),
    description=_(
        "The current organization's plan, status, trial end and usage against "
        'its limits. Owner and Admin only.'
    ),
    responses={200: SubscriptionDetailSerializer},
)
class SubscriptionView(OrganizationScopedRequestMixin, APIView):
    permission_classes = [BillingPermission]

    def get(self, request, *args, **kwargs):
        organization = self.auth_organization
        subscription = (
            Subscription.objects.select_related('plan')
            .filter(organization=organization)
            .first()
        )
        if subscription is None:
            raise InvalidState(_('This organization has no subscription.'))
        data = {
            'plan': subscription.plan,
            'status': subscription.status,
            'cycle': subscription.cycle,
            'trial_ends_at': subscription.trial_ends_at,
            'is_complimentary': subscription.is_complimentary,
            'usage': selectors.usage(organization),
        }
        return Response(
            SubscriptionDetailSerializer(data).data, status=status.HTTP_200_OK
        )
