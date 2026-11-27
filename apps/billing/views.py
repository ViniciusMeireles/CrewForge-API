import logging
from collections.abc import Callable
from typing import cast

from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import Action, authorize
from apps.accounts.mixins.requests import OrganizationScopedRequestMixin
from apps.billing import payments, selectors
from apps.billing.authentication import AsaasWebhookAuthentication
from apps.billing.choices import BillingCycleChoices, GatewayChoices
from apps.billing.gateways.asaas import AsaasGateway
from apps.billing.models.gateway_event import GatewayEvent
from apps.billing.models.invoice import Invoice
from apps.billing.models.plan import Plan
from apps.billing.models.subscription import Subscription
from apps.billing.permissions import BillingManagePermission, BillingPermission
from apps.billing.serializers import (
    BillingProfileSerializer,
    ChangePreviewSerializer,
    ChangeRequestSerializer,
    ChangeResultSerializer,
    InvoiceSerializer,
    PlanSerializer,
    SubscriptionDetailSerializer,
)
from apps.billing.tasks import process_gateway_event
from apps.generics.errors import InvalidState

logger = logging.getLogger(__name__)

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
        return Response(_detail(self, _subscription(self)), status=status.HTTP_200_OK)


def _can_manage(view) -> bool:
    return authorize(view.auth_member, Action.BILLING_MANAGE)


def _detail(view, subscription: Subscription) -> dict:
    data = selectors.subscription_detail(subscription, can_manage=_can_manage(view))
    return SubscriptionDetailSerializer(data).data


def _subscription(view) -> Subscription:
    subscription = (
        Subscription.objects.select_related(
            'plan', 'organization', 'scheduled_plan', 'pending_plan'
        )
        .filter(organization=view.auth_organization)
        .first()
    )
    if subscription is None:
        raise InvalidState(_('This organization has no subscription.'))
    return subscription


@extend_schema(
    tags=BILLING_TAGS,
    summary=_('Preview a plan change'),
    description=_(
        'What a change to the given plan and cycle charges now and from when. '
        'Owner only.'
    ),
    parameters=[
        OpenApiParameter('plan', str, required=True),
        OpenApiParameter('cycle', str, required=True, enum=BillingCycleChoices.values),
    ],
    responses={200: ChangePreviewSerializer},
)
class SubscriptionPreviewView(OrganizationScopedRequestMixin, APIView):
    permission_classes = [BillingManagePermission]

    def get(self, request, *args, **kwargs):
        serializer = ChangeRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        preview = payments.preview_change(
            _subscription(self),
            serializer.validated_data['plan'],
            serializer.validated_data['cycle'],
        )
        return Response(ChangePreviewSerializer(preview).data)


@extend_schema(
    tags=BILLING_TAGS,
    summary=_('Change the plan'),
    description=_(
        'Changes the plan or cycle. Returns the payment page when something is due '
        'now. Owner only.'
    ),
    request=ChangeRequestSerializer,
    responses={200: ChangeResultSerializer},
)
class SubscriptionChangeView(OrganizationScopedRequestMixin, APIView):
    permission_classes = [BillingManagePermission]

    def post(self, request, *args, **kwargs):
        serializer = ChangeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _subscription_changed, payment_url = payments.change_plan(
            self.auth_organization,
            serializer.validated_data['plan'],
            serializer.validated_data['cycle'],
            request=request,
            actor_member=self.auth_member,
        )
        return Response(
            {
                'subscription': _detail(self, _subscription(self)),
                'payment_url': payment_url,
            }
        )


class _SubscriptionActionView(OrganizationScopedRequestMixin, APIView):
    permission_classes = [BillingManagePermission]
    action_function: Callable[..., Subscription]

    def post(self, request, *args, **kwargs):
        type(self).action_function(
            self.auth_organization, request=request, actor_member=self.auth_member
        )
        return Response(_detail(self, _subscription(self)))


@extend_schema(
    tags=BILLING_TAGS,
    summary=_('Cancel the subscription'),
    description=_('Schedules the cancellation for the end of the paid period.'),
    request=None,
    responses={200: SubscriptionDetailSerializer},
)
class SubscriptionCancelView(_SubscriptionActionView):
    action_function = payments.cancel


@extend_schema(
    tags=BILLING_TAGS,
    summary=_('Resume the subscription'),
    description=_('Undoes a scheduled cancellation or downgrade.'),
    request=None,
    responses={200: SubscriptionDetailSerializer},
)
class SubscriptionResumeView(_SubscriptionActionView):
    action_function = payments.resume


@extend_schema(
    tags=BILLING_TAGS,
    summary=_('Discard the pending change'),
    description=_('Cancels a plan change that waits for its payment.'),
    request=None,
    responses={200: SubscriptionDetailSerializer},
)
class SubscriptionDiscardChangeView(_SubscriptionActionView):
    action_function = payments.discard_change


class BillingProfileView(OrganizationScopedRequestMixin, APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [BillingPermission()]
        return [BillingManagePermission()]

    def _context(self) -> dict:
        return {'can_manage': _can_manage(self)}

    @extend_schema(
        tags=BILLING_TAGS,
        summary=_('Get billing details'),
        responses={200: BillingProfileSerializer},
    )
    def get(self, request, *args, **kwargs):
        profile = payments.billing_profile(self.auth_organization)
        if profile is None:
            raise NotFound(_('No billing details yet.'))
        return Response(BillingProfileSerializer(profile, context=self._context()).data)

    @extend_schema(
        tags=BILLING_TAGS,
        summary=_('Save billing details'),
        request=BillingProfileSerializer,
        responses={200: BillingProfileSerializer},
    )
    def put(self, request, *args, **kwargs):
        serializer = BillingProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = payments.upsert_profile(
            self.auth_organization,
            serializer.validated_data,
            request=request,
            actor_member=self.auth_member,
        )
        return Response(BillingProfileSerializer(profile, context=self._context()).data)


@extend_schema(
    tags=BILLING_TAGS,
    summary=_('List invoices'),
    description=_('The organization invoices, newest first. Owner and Admin.'),
)
class InvoiceListView(OrganizationScopedRequestMixin, ListAPIView):
    permission_classes = [BillingPermission]
    serializer_class = InvoiceSerializer
    filter_backends: list = []

    def get_queryset(self):
        return Invoice.objects.filter(
            subscription__organization=self.auth_organization
        ).order_by('-issued_at', '-id')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'can_manage': _can_manage(self)}


@extend_schema(exclude=True)
class AsaasWebhookView(APIView):
    authentication_classes = [AsaasWebhookAuthentication]
    permission_classes = [AllowAny]
    throttle_classes: list = []

    def post(self, request, *args, **kwargs):
        body = request.data if isinstance(request.data, dict) else {}
        webhook = AsaasGateway().parse_webhook(body)
        if webhook is None:
            logger.warning('billing.webhook_unparsed')
            return Response({})
        try:
            with transaction.atomic():
                event, created = GatewayEvent.objects.get_or_create(
                    gateway=GatewayChoices.ASAAS,
                    event_id=webhook.event_id,
                    defaults={'event_type': webhook.event_type, 'payload': body},
                )
        except IntegrityError:
            return Response({})
        if created:
            transaction.on_commit(lambda: process_gateway_event.delay(event.pk))
        return Response({})
