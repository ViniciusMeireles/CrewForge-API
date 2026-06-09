from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.generics.managers.querysets import BaseManager, BaseQuerySet


class BaseModel(models.Model):
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('Is this record active or not'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
        help_text=_('When the record was initially created'),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At'),
        help_text=_('When the record was last updated'),
    )
    created_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Created By'),
        help_text=_('User who created the record'),
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Updated By'),
        help_text=_('User who last updated the record'),
        null=True,
        blank=True,
    )

    objects = BaseManager.from_queryset(BaseQuerySet)

    class Meta:
        abstract = True

    def activate(self):
        self.is_active = True
        self.save()

    def inactivate(self):
        self.is_active = False
        self.save()

    @classmethod
    def schema_tags(cls):
        """Returns the schema tags for the model for documentation purposes."""
        return [cls._meta.verbose_name_plural.capitalize()]
