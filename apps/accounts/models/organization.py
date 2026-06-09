from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.choices import OrganizationImageTypeChoices
from apps.accounts.managers.organization import (
    OrganizationManager,
    OrganizationProfileManager,
)
from apps.accounts.managers.organization_image import OrganizationImageManager
from apps.generics.models.abstracts import BaseModel


class Organization(BaseModel):
    name = models.CharField(
        max_length=255, verbose_name=_('Name'), help_text=_('Organization name')
    )
    slug = models.SlugField(
        unique=True, verbose_name=_('Slug'), help_text=_('Organization slug')
    )
    owner = models.ForeignKey(
        to='accounts.Member',
        on_delete=models.SET_NULL,
        related_name='owned_organizations',
        verbose_name=_('Owner'),
        help_text=_('Owner of the organization'),
        null=True,
        blank=True,
    )

    objects = OrganizationManager()

    class Meta:
        ordering = ['-id']
        verbose_name = _('Organization')
        verbose_name_plural = _('Organizations')

    def __str__(self):
        return self.name

    @property
    def members(self):
        from apps.accounts.models.member import Member

        if not self.id:
            return Member.objects.none()
        return Member.objects.filter(
            organization_id=self.id,
            is_active=True,
        )

    def get_profile(self) -> OrganizationProfile:
        return OrganizationProfile.objects.get_or_create(organization=self)[0]


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
