from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.billing.choices import GatewayChoices
from apps.billing.managers import GatewayEventQuerySet


class GatewayEvent(models.Model):
    gateway = models.CharField(
        max_length=20, choices=GatewayChoices.choices, verbose_name=_('Gateway')
    )
    event_id = models.CharField(max_length=64, verbose_name=_('Event id'))
    event_type = models.CharField(max_length=64, verbose_name=_('Event type'))
    payload = models.JSONField(default=dict, verbose_name=_('Payload'))
    received_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Received at'))
    processed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('Processed at')
    )
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name=_('Attempts'))
    error = models.TextField(blank=True, default='', verbose_name=_('Error'))

    objects = GatewayEventQuerySet.as_manager()

    class Meta:
        ordering = ['-received_at']
        verbose_name = _('Gateway event')
        verbose_name_plural = _('Gateway events')
        constraints = [
            models.UniqueConstraint(
                fields=['gateway', 'event_id'], name='billing_gateway_event_unique'
            ),
        ]

    def __str__(self) -> str:
        return f'{self.gateway}:{self.event_id} · {self.event_type}'

    @property
    def payment_id(self) -> str:
        payment = (
            self.payload.get('payment') if isinstance(self.payload, dict) else None
        )
        if isinstance(payment, dict):
            return str(payment.get('id') or '')
        return ''
