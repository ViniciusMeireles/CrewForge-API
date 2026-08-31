from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.generics.models.abstracts import BaseModel
from apps.{app}.managers.{resource} import {Resource}Manager


class {Resource}(BaseModel):
    {fields}

    objects = {Resource}Manager()

    class Meta:
        ordering = ['-id']
        verbose_name = _('{Resource}')
        verbose_name_plural = _('{Resources}')
        {unique_together}

    def __str__(self):
        return self.{str_field}

    {label_expression}
