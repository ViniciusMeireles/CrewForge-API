import hmac
import logging

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.generics.utils.requests import client_ip

logger = logging.getLogger(__name__)

HEADER = 'HTTP_ASAAS_ACCESS_TOKEN'


class AsaasWebhookAuthentication(BaseAuthentication):
    """The shared-secret header Asaas sends with every webhook (ADR-014)."""

    def authenticate(self, request):
        expected = settings.ASAAS_WEBHOOK_TOKEN
        received = request.META.get(HEADER, '')
        if (
            not expected
            or not received
            or not hmac.compare_digest(received.encode(), expected.encode())
        ):
            logger.warning('billing.webhook_rejected', extra={'ip': client_ip(request)})
            raise AuthenticationFailed(_('Invalid webhook token.'))
        return (None, 'asaas')

    def authenticate_header(self, request):
        return 'asaas-access-token'
