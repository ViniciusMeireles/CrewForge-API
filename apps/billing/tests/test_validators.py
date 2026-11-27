from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.billing.factories.payments import VALID_CNPJ, VALID_CPF
from apps.billing.models.billing_profile import BillingProfile
from apps.billing.validators import (
    is_valid_tax_id,
    normalize_digits,
    validate_postal_code,
    validate_tax_id,
)


class TaxIdTestCase(SimpleTestCase):
    def test_valid_cpf_and_cnpj_with_or_without_punctuation(self):
        for value in (VALID_CPF, '529.982.247-25', VALID_CNPJ, '11.222.333/0001-81'):
            with self.subTest(value=value):
                self.assertTrue(is_valid_tax_id(value))

    def test_invalid_check_digits_lengths_and_repeated_digits(self):
        for value in ('52998224724', '11222333000180', '11111111111', '123', ''):
            with self.subTest(value=value):
                self.assertFalse(is_valid_tax_id(value))
                with self.assertRaisesMessage(
                    ValidationError, 'Enter a valid CPF or CNPJ.'
                ):
                    validate_tax_id(value)

    def test_normalize_digits(self):
        self.assertEqual(normalize_digits('01001-000'), '01001000')
        self.assertEqual(normalize_digits(None), '')

    def test_postal_code(self):
        validate_postal_code('01001-000')
        for value in ('0100-100', '010010000', ''):
            with (
                self.subTest(value=value),
                self.assertRaisesMessage(
                    ValidationError, 'Enter an 8-digit postal code.'
                ),
            ):
                validate_postal_code(value)


class MaskTestCase(SimpleTestCase):
    def test_masks(self):
        self.assertEqual(
            BillingProfile(tax_id=VALID_CNPJ).masked_tax_id, 'CNPJ 11.222.333/0001-**'
        )
        self.assertEqual(
            BillingProfile(tax_id=VALID_CPF).masked_tax_id, 'CPF 529.982.***-**'
        )
        self.assertEqual(BillingProfile(tax_id=VALID_CPF).tax_id_kind, 'cpf')
