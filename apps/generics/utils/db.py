from django.apps import apps
from django.db import IntegrityError


def get_constraint_violation_message(exc: IntegrityError) -> str | None:
    """
    Return the ``violation_error_message`` of the model constraint that raised
    ``exc``, or ``None`` when the constraint is not a known model constraint.

    The constraint name comes from the PostgreSQL error (psycopg ``diag``).
    """
    diag = getattr(exc.__cause__, 'diag', None)
    if not (constraint_name := getattr(diag, 'constraint_name', None)):
        return None
    for model in apps.get_models():
        for constraint in model._meta.constraints:
            if constraint.name == constraint_name:
                return constraint.get_violation_error_message()
    return None
