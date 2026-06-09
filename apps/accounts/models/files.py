import mimetypes
import os

import uuid6
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.reverse import reverse

from apps.accounts.choices import StoredFileAccess
from apps.accounts.managers.files import StoredFileManager
from apps.generics.models.abstracts import BaseModel


def upload_to_storage_files(instance, filename):
    current_date = timezone.now()
    guessed_type, _ = mimetypes.guess_type(filename)
    content_type = guessed_type or instance.content_type or 'application/octet-stream'
    new_filename = str(instance.uuid)
    if '.' in filename:
        new_filename += os.path.splitext(filename)[1]
    return (
        f'stored/files/{content_type}/'
        f'{current_date.strftime("%Y")}/'
        f'{current_date.strftime("%m")}/'
        f'{current_date.strftime("%d")}/'
        f'{new_filename}'
    )


class StoredFile(BaseModel):
    uuid = models.UUIDField(
        default=uuid6.uuid7,
        unique=True,
        db_index=True,
        editable=False,
        verbose_name=_('UUID'),
        help_text=_('Unique identifier for the file'),
    )
    file = models.FileField(
        upload_to=upload_to_storage_files,
        verbose_name=_('File'),
        help_text=_('File to be stored'),
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Name'),
        help_text=_('Name of the file'),
    )
    original_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Original Name'),
        help_text=_('Original name of the file'),
    )
    content_type = models.CharField(
        max_length=100,
        verbose_name=_('Content Type'),
        help_text=_('Content type of the file'),
        blank=True,
    )
    size = models.PositiveBigIntegerField(
        default=0,
        verbose_name=_('Size'),
        help_text=_('Size of the file'),
    )
    viewing_permission = models.CharField(
        max_length=30,
        choices=StoredFileAccess.choices,
        default=StoredFileAccess.OWNER,
        verbose_name=_('Viewing Permission'),
        help_text=_('Access level for viewing the file'),
    )
    updating_permission = models.CharField(
        max_length=30,
        choices=StoredFileAccess.choices,
        default=StoredFileAccess.OWNER,
        verbose_name=_('Updating Permission'),
        help_text=_('Access level for updating the file'),
    )
    owner = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stored_files',
        verbose_name=_('Owner'),
        help_text=_('Owner of the file'),
        null=True,
        blank=True,
    )
    organization = models.ForeignKey(
        to='accounts.Organization',
        on_delete=models.CASCADE,
        related_name='stored_files',
        null=True,
        blank=True,
        verbose_name=_('Organization'),
        help_text=_('Organization to which the file belongs'),
    )

    objects = StoredFileManager()

    class Meta:
        ordering = ['-id']
        verbose_name = _('Stored File')
        verbose_name_plural = _('Stored Files')

    def __str__(self):
        return f'{self.uuid} - {self.name or self.original_name}'

    @property
    def download_name(self) -> str:
        """Return the name to download the file."""
        name = (self.name or self.original_name or str(self.uuid)).strip()
        if '.' not in name:
            extension = mimetypes.guess_extension(
                type=self.content_type or 'application/octet-stream'
            )
            if extension and (extension != '.bin' and '.bin' not in self.original_name):
                name += extension
        return name

    @property
    def file_path(self) -> str:
        """Return the path to download the file."""
        return str(reverse(viewname='accounts:stored_files-file', args=[self.uuid]))

    @classmethod
    def label_expression(
        cls, outer_ref: str | None = None
    ) -> models.expressions.Combinable:
        """
        Define the label expression for the stored file model.
        This is used to generate the label of the stored file
        """
        name = f'{outer_ref}__name' if outer_ref else 'name'
        original_name = f'{outer_ref}__original_name' if outer_ref else 'original_name'
        label_expression = models.Case(
            models.When(
                condition=models.Q(
                    ~models.Q(**{name: ''}),
                    **{f'{name}__isnull': False},
                ),
                then=models.F(name),
            ),
            default=models.F(original_name),
        )
        return label_expression

    def save(self, *args, **kwargs):
        if self.file:
            if not self.original_name:
                self.original_name = self.file.name.split('/')[-1]

            guessed_type, _ = mimetypes.guess_type(self.file.name)
            content_type = guessed_type or 'application/octet-stream'
            if content_type and (
                not self.content_type or self.content_type != content_type
            ):
                self.content_type = content_type

            try:
                size = self.file.size
            except ValueError:
                size = 0
            if size and (not self.size or self.size != size):
                self.size = size

        super().save(*args, **kwargs)
