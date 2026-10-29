from functools import cached_property

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.choices import (
    MemberRoleChoices,
    OrganizationImageTypeChoices,
    OrganizationStatusChoices,
)
from apps.accounts.managers.organization import (
    OrganizationManager,
    OrganizationProfileManager,
)
from apps.accounts.managers.organization_image import OrganizationImageManager
from apps.generics.models.abstracts import BaseModel

LOGO_PRIORITY = {
    OrganizationImageTypeChoices.LOGO_LIGHT: 0,
    OrganizationImageTypeChoices.LOGO: 1,
    OrganizationImageTypeChoices.LOGO_DARK: 2,
}


class Organization(BaseModel):
    name = models.CharField(
        max_length=255, verbose_name=_('Name'), help_text=_('Organization name')
    )
    slug = models.SlugField(
        unique=True, verbose_name=_('Slug'), help_text=_('Organization slug')
    )
    status = models.CharField(
        max_length=16,
        choices=OrganizationStatusChoices.choices,
        default=OrganizationStatusChoices.ACTIVE,
        db_index=True,
        verbose_name=_('Status'),
        help_text=_('Suspended organizations cannot be entered'),
    )
    suspended_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Suspended At'),
        help_text=_('When the organization was suspended'),
    )
    suspended_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
        blank=True,
        verbose_name=_('Suspended By'),
        help_text=_('Platform admin who suspended the organization'),
    )
    suspension_reason = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Suspension Reason'),
        help_text=_('Internal reason, never shown to members'),
    )

    objects = OrganizationManager()

    class Meta:
        ordering = ['-id']
        verbose_name = _('Organization')
        verbose_name_plural = _('Organizations')

    def __str__(self):
        return self.name

    @cached_property
    def owner(self):
        if hasattr(self, 'active_owners'):
            return self.active_owners[0] if self.active_owners else None
        return (
            self.members.filter(role=MemberRoleChoices.OWNER, is_active=True)
            .select_related('user')
            .first()
        )

    def refresh_from_db(self, *args, **kwargs):
        self.__dict__.pop('owner', None)
        self.__dict__.pop('active_owners', None)
        super().refresh_from_db(*args, **kwargs)

    @property
    def is_suspended(self) -> bool:
        return self.status == OrganizationStatusChoices.SUSPENDED

    def get_profile(self) -> OrganizationProfile | None:
        try:
            return self.profile
        except OrganizationProfile.DoesNotExist:
            return None


class OrganizationProfile(BaseModel):
    organization = models.OneToOneField(
        to='accounts.Organization',
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_('Organization'),
        help_text=_('Organization to which this profile belongs'),
    )
    website = models.URLField(
        null=True,
        blank=True,
        verbose_name=_('Website'),
        help_text=_('Organization website'),
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Organization description'),
    )

    objects = OrganizationProfileManager()

    class Meta:
        ordering = ['-id']
        verbose_name = _('Organization Profile')
        verbose_name_plural = _('Organization Profiles')

    def __str__(self):
        return f'{self.organization}'

    def get_logo_obj(self, dark_priority: bool) -> OrganizationImage | None:
        if hasattr(self, 'logo_images'):
            logos = sorted(
                self.logo_images,
                key=lambda image: (LOGO_PRIORITY.get(image.image_type, 1), image.pk),
            )
        else:
            logos = sorted(
                self.images.filter(image_type__in=LOGO_PRIORITY, is_active=True),
                key=lambda image: (LOGO_PRIORITY.get(image.image_type, 1), image.pk),
            )
        if not logos:
            return None
        return logos[-1] if dark_priority else logos[0]


class OrganizationImage(BaseModel):
    profile = models.ForeignKey(
        to=OrganizationProfile,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_('Profile'),
        help_text=_('Organization profile'),
    )
    image_type = models.CharField(
        max_length=32,
        choices=OrganizationImageTypeChoices.choices,
        default=OrganizationImageTypeChoices.LOGO,
        verbose_name=_('Image type'),
        help_text=_('Type of organization image'),
    )
    image = models.OneToOneField(
        to='accounts.StoredFile',
        on_delete=models.CASCADE,
        related_name='+',
        verbose_name=_('Image'),
        help_text=_('Organization image'),
    )

    objects = OrganizationImageManager()

    class Meta:
        verbose_name = _('Organization Image')
        verbose_name_plural = _('Organization Images')
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['profile', 'image_type'],
                name='unique_profile_image_type',
                condition=models.Q(is_active=True),
                violation_error_message=_(
                    'An image of this type already exists for this profile.'
                ),
            ),
        ]

    def __str__(self):
        return f'{self.profile} - {self.image_type}'

    @classmethod
    def label_expression(cls):
        return models.F('image_type')
