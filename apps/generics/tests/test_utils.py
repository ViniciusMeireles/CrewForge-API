from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError
from django.test import SimpleTestCase

from apps.generics.utils.db import get_constraint_violation_message
from apps.generics.utils.models import get_verbose_name_field
from apps.generics.utils.serializers import get_user_of_context
from apps.generics.utils.strings import str_to_bool
from apps.teams.models.team import Team


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


class GetVerboseNameFieldTestCase(SimpleTestCase):
    def test_model_field(self):
        self.assertEqual(get_verbose_name_field(Team, 'name'), 'Name')

    def test_unknown_field_returns_field_name(self):
        self.assertEqual(get_verbose_name_field(Team, 'unknown'), 'unknown')

    def test_non_model_returns_field_name(self):
        self.assertEqual(get_verbose_name_field(object, 'name'), 'name')


class GetUserOfContextTestCase(SimpleTestCase):
    def _context(self, user):
        return {'request': SimpleNamespace(user=user)}

    def test_without_request(self):
        self.assertIsNone(get_user_of_context({}))

    def test_without_user(self):
        self.assertIsNone(get_user_of_context(self._context(None)))

    def test_anonymous_user(self):
        self.assertIsNone(get_user_of_context(self._context(AnonymousUser())))

    def test_inactive_user(self):
        user = SimpleNamespace(is_authenticated=True, is_active=False)
        self.assertIsNone(get_user_of_context(self._context(user)))

    def test_active_user(self):
        user = SimpleNamespace(is_authenticated=True, is_active=True)
        self.assertIs(get_user_of_context(self._context(user)), user)


class GetConstraintViolationMessageTestCase(SimpleTestCase):
    def _integrity_error(self, constraint_name):
        cause = Exception('database error')
        cause.diag = SimpleNamespace(constraint_name=constraint_name)
        exc = IntegrityError('violation')
        exc.__cause__ = cause
        return exc

    def test_known_constraint(self):
        exc = self._integrity_error('unique_name_org_when_active')
        self.assertEqual(
            get_constraint_violation_message(exc), 'This team already exists.'
        )

    def test_unknown_constraint(self):
        exc = self._integrity_error('unknown_constraint')
        self.assertIsNone(get_constraint_violation_message(exc))

    def test_without_diagnostics(self):
        self.assertIsNone(get_constraint_violation_message(IntegrityError('x')))
