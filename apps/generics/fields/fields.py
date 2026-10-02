import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.functional import cached_property

from apps.generics.utils.serializers import get_user_of_context

User = get_user_model()

log = logging.getLogger(__name__)


# Python type of the values produced by each Django model field. Used to type
# option values (JSON output and OpenAPI schema).
FIELD_PYTHON_TYPES = {
    models.AutoField: int,
    models.BigAutoField: int,
    models.SmallAutoField: int,
    models.IntegerField: int,
    models.BigIntegerField: int,
    models.PositiveIntegerField: int,
    models.PositiveBigIntegerField: int,
    models.PositiveSmallIntegerField: int,
    models.SmallIntegerField: int,
    models.CharField: str,
    models.TextField: str,
    models.BooleanField: bool,
    models.FloatField: float,
    models.DecimalField: Decimal,
    models.DateField: date,
    models.DateTimeField: datetime,
    models.TimeField: time,
    models.JSONField: dict | list,
    models.UUIDField: str,
    models.DurationField: timedelta,
    models.GenericIPAddressField: str,
    models.FilePathField: str,
}


def get_python_type(field: models.Field) -> type:
    """
    Return the Python type for a model field.

    An exact class match wins; otherwise the type of a mapped parent class is
    used (e.g. a custom ``CharField`` subclass maps to ``str``). Unmapped fields
    fall back to ``str``, which is always JSON-safe.
    """
    secondary_python_type = None
    for field_class, python_type in FIELD_PYTHON_TYPES.items():
        if isinstance(field, field_class):
            if type(field) is field_class:
                return python_type
            secondary_python_type = python_type
    if secondary_python_type:
        return secondary_python_type
    log.warning(
        'Python type not mapped for field type %s; using str', type(field).__name__
    )
    return str


class AuthUserFieldMixin:
    @cached_property
    def auth_user(self) -> User | None:
        """Get the user from the context."""
        return get_user_of_context(self.context)
