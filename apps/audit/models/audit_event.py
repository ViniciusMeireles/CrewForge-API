from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.managers.audit_event import AuditEventManager


class AuditEvent(models.Model):
    created_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        verbose_name=_('Created At'),
        help_text=_('When the event happened'),
    )
    organization = models.ForeignKey(
        to='accounts.Organization',
        on_delete=models.SET_NULL,
        related_name='audit_events',
        null=True,
        blank=True,
        verbose_name=_('Organization'),
        help_text=_('Organization of the event; empty for account events'),
    )
    organization_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Organization Name'),
        help_text=_('Organization name when the event happened'),
    )
    action = models.CharField(
        max_length=64,
        choices=AuditActionChoices.choices,
        verbose_name=_('Action'),
        help_text=_('What happened'),
    )
    actor_type = models.CharField(
        max_length=16,
        choices=AuditActorTypeChoices.choices,
        default=AuditActorTypeChoices.USER,
        verbose_name=_('Actor Type'),
        help_text=_('Who performed the action'),
    )
    actor_user = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
        blank=True,
        verbose_name=_('Actor User'),
        help_text=_('User who performed the action'),
    )
    actor_member = models.ForeignKey(
        to='accounts.Member',
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
        blank=True,
        verbose_name=_('Actor Member'),
        help_text=_('Member who performed the action'),
    )
    actor_label = models.CharField(
        max_length=300,
        blank=True,
        verbose_name=_('Actor Label'),
        help_text=_('Actor name when the event happened'),
    )
    subject_user = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='account_audit_events',
        null=True,
        blank=True,
        verbose_name=_('Subject User'),
        help_text=_('User an account event belongs to'),
    )
    subject_label = models.CharField(
        max_length=300,
        blank=True,
        verbose_name=_('Subject Label'),
        help_text=_('Subject user (email and name) when the event happened'),
    )
    impersonator = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
        blank=True,
        verbose_name=_('Impersonator'),
        help_text=_('Platform user acting as the actor'),
    )
    target_type = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_('Target Type'),
        help_text=_('Kind of record the action applies to'),
    )
    target_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_('Target ID'),
        help_text=_('Identifier of the record the action applies to'),
    )
    target_label = models.CharField(
        max_length=300,
        blank=True,
        verbose_name=_('Target Label'),
        help_text=_('Record name when the event happened'),
    )
    changes = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Changes'),
        help_text=_('Changed fields with their values before and after'),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Extra context of the event'),
    )
    ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address'),
        help_text=_('Client address of the request'),
    )

    objects = AuditEventManager()

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = _('Audit Event')
        verbose_name_plural = _('Audit Events')
        indexes = [
            models.Index(
                fields=['organization', '-created_at'],
                name='audit_org_created_idx',
            ),
            models.Index(
                fields=['organization', 'action', '-created_at'],
                name='audit_org_action_idx',
            ),
            models.Index(
                fields=['organization', 'target_type', 'target_id'],
                name='audit_org_target_idx',
            ),
            models.Index(
                fields=['subject_user', '-created_at'],
                name='audit_subject_created_idx',
            ),
            models.Index(fields=['created_at'], name='audit_created_idx'),
        ]

    def __str__(self):
        return f'{self.action} - {self.target_label or self.actor_label}'

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError('Audit events are immutable.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError('Audit events are immutable.')

    @classmethod
    def schema_tags(cls):
        return [_('Audit')]
