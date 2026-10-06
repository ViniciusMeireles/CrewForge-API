from types import SimpleNamespace

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.accounts.factories.users import UserFactory
from apps.accounts.serializers.user import UserSerializer


def _context(user=None):
    return {'request': SimpleNamespace(user=user)} if user else {}


def _payload(**overrides):
    data = UserFactory.build()
    payload = {
        'username': data.username,
        'email': data.email,
        'first_name': data.first_name,
        'last_name': data.last_name,
        'password': 'NewPassWord*123',
    }
    payload.update(overrides)
    return payload


class UserSerializerPasswordTestCase(TestCase):
    def test_empty_password_on_update(self):
        user = UserFactory()
        serializer = UserSerializer(instance=user, context=_context(user))
        with self.assertRaises(ValidationError):
            serializer.validate_password('')

    def test_password_change_by_another_user(self):
        user = UserFactory()
        serializer = UserSerializer(instance=user, context=_context(UserFactory()))
        with self.assertRaises(ValidationError):
            serializer.validate_password('NewPassWord*123')

    def test_password_change_by_the_user(self):
        user = UserFactory()
        serializer = UserSerializer(instance=user, context=_context(user))
        self.assertEqual(
            serializer.validate_password('NewPassWord*123'), 'NewPassWord*123'
        )


class UserSerializerIsValidTestCase(TestCase):
    def test_new_user_is_valid(self):
        serializer = UserSerializer(data=_payload())
        self.assertTrue(serializer.is_valid())

    def test_existing_username_is_invalid(self):
        existing = UserFactory()
        serializer = UserSerializer(data=_payload(username=existing.username))
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)

    def test_existing_username_raises(self):
        existing = UserFactory()
        serializer = UserSerializer(data=_payload(username=existing.username))
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_invalid_data_raises(self):
        serializer = UserSerializer(data=_payload(email='not-an-email'))
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_own_username_on_update_is_valid(self):
        user = UserFactory()
        serializer = UserSerializer(
            instance=user,
            data={'username': user.username},
            partial=True,
            context=_context(user),
        )
        self.assertTrue(serializer.is_valid())


class UserSerializerSaveTestCase(TestCase):
    def test_create_hashes_password(self):
        serializer = UserSerializer(data=_payload())
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        self.assertTrue(user.check_password('NewPassWord*123'))

    def test_create_without_password(self):
        payload = _payload()
        del payload['password']
        serializer = UserSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        self.assertFalse(user.has_usable_password() and user.check_password(''))

    def test_update_hashes_password(self):
        user = UserFactory()
        serializer = UserSerializer(
            instance=user,
            data={'password': 'Changed*123'},
            partial=True,
            context=_context(user),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        user.refresh_from_db()
        self.assertTrue(user.check_password('Changed*123'))

    def test_update_without_password_keeps_it(self):
        user = UserFactory()
        serializer = UserSerializer(
            instance=user,
            data={'first_name': 'Renamed'},
            partial=True,
            context=_context(user),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Renamed')
        self.assertTrue(user.check_password('passWord*123'))
