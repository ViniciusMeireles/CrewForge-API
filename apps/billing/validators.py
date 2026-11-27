import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

CPF_LENGTH = 11
CNPJ_LENGTH = 14
POSTAL_CODE_LENGTH = 8
CNPJ_MIN_REMAINDER = 2
_CNPJ_WEIGHTS_FIRST = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_CNPJ_WEIGHTS_SECOND = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def normalize_digits(value: str | None) -> str:
    return re.sub(r'\D', '', value or '')


def _cpf_is_valid(digits: str) -> bool:
    if len(digits) != CPF_LENGTH or len(set(digits)) == 1:
        return False
    for size in (9, 10):
        total = sum(
            int(d) * w
            for d, w in zip(digits[:size], range(size + 1, 1, -1), strict=False)
        )
        check = (total * 10) % 11 % 10
        if check != int(digits[size]):
            return False
    return True


def _cnpj_is_valid(digits: str) -> bool:
    if len(digits) != CNPJ_LENGTH or len(set(digits)) == 1:
        return False
    for weights, position in ((_CNPJ_WEIGHTS_FIRST, 12), (_CNPJ_WEIGHTS_SECOND, 13)):
        total = sum(
            int(d) * w for d, w in zip(digits[:position], weights, strict=False)
        )
        remainder = total % 11
        check = 0 if remainder < CNPJ_MIN_REMAINDER else 11 - remainder
        if check != int(digits[position]):
            return False
    return True


def is_valid_tax_id(value: str) -> bool:
    digits = normalize_digits(value)
    return _cpf_is_valid(digits) or _cnpj_is_valid(digits)


def validate_tax_id(value: str) -> None:
    if not is_valid_tax_id(value):
        raise ValidationError(_('Enter a valid CPF or CNPJ.'), code='invalid_tax_id')


def validate_postal_code(value: str) -> None:
    if len(normalize_digits(value)) != POSTAL_CODE_LENGTH:
        raise ValidationError(
            _('Enter an 8-digit postal code.'), code='invalid_postal_code'
        )
