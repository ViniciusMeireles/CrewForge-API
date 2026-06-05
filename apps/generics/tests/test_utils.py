from django.test import SimpleTestCase

from apps.generics.utils.strings import str_to_bool


class StrToBoolTestCase(SimpleTestCase):
    def test_true_values(self):
        truthy_inputs = ['true', 'yes', '1', 'y', 'on', 't']
        for value in truthy_inputs:
            with self.subTest(value=value):
                self.assertTrue(str_to_bool(value))

    def test_true_case_insensitive(self):
        self.assertTrue(str_to_bool('True'))
        self.assertTrue(str_to_bool('TRUE'))
        self.assertTrue(str_to_bool('YeS'))
        self.assertTrue(str_to_bool('ON'))

    def test_false_values(self):
        falsy_inputs = ['false', '0', 'no', 'off', 'f', 'n', 'random', 'abc']
        for value in falsy_inputs:
            with self.subTest(value=value):
                self.assertFalse(str_to_bool(value))

    def test_none_returns_false(self):
        self.assertFalse(str_to_bool(None))

    def test_empty_string_returns_false(self):
        self.assertFalse(str_to_bool(''))
