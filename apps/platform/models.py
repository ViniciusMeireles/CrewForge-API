from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.platform.choices import ImpersonationEndReasonChoices


class ImpersonationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(ended_at__isnull=True)


class Impersonation(models.Model):
    staff = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='impersonations_started',
        verbose_name=_('Staff'),
        help_text=_('Platform staff member viewing as the target'),
    )
    target = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='impersonations_received',
        verbose_name=_('Target'),
        help_text=_('User being viewed'),
    )
    reason = models.CharField(
        max_length=500,
        verbose_name=_('Reason'),
        help_text=_('Why the staff member views as the target'),
    )
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Started At'),
        help_text=_('When the viewing session started'),
    )
    expires_at = models.DateTimeField(
        verbose_name=_('Expires At'),
        help_text=_('When the viewing session ends at the latest'),
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Ended At'),
        help_text=_('When the viewing session ended'),
    )
    end_reason = models.CharField(
        max_length=16,
        choices=ImpersonationEndReasonChoices.choices,
        blank=True,
        verbose_name=_('End Reason'),
        help_text=_('Why the viewing session ended'),
    )

    objects = ImpersonationQuerySet.as_manager()

    class Meta:
        verbose_name = _('Impersonation')
        verbose_name_plural = _('Impersonations')
        ordering = ['-started_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['staff'],
                condition=Q(ended_at__isnull=True),
                name='unique_active_impersonation_per_staff',
                violation_error_message=_(
                    'You already have an active viewing session.'
                ),
            ),
        ]
        indexes = [models.Index(fields=['target', 'ended_at'])]

    def __str__(self) -> str:
        return f'{self.staff} → {self.target}'

    @property
    def is_active(self) -> bool:
        return self.ended_at is None

    def is_expired(self, now=None) -> bool:
        return (now or timezone.now()) >= self.expires_at
