from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rest_framework.test import APITestCase

from apps.accounts.factories.users import UserFactory
from apps.accounts.serializers.user_profile import (
    ChangePasswordSerializer,
    UserProfileSerializer,
)

User = get_user_model()


class UserProfileSerializerTestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory.create()

    def _get_serializer_context(self):
        request = RequestFactory().get('/')
        request.user = self.user
        return {'request': request}

    def test_contains_expected_fields(self):
        serializer = UserProfileSerializer(
            instance=self.user,
            context=self._get_serializer_context(),
        )
        expected_fields = {'id', 'username', 'email', 'first_name', 'last_name'}
        self.assertEqual(set(serializer.data.keys()), expected_fields)

    def test_username_is_read_only(self):
        serializer = UserProfileSerializer(
            instance=self.user,
            data={'username': 'new-username'},
            partial=True,
            context=self._get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        self.assertNotIn('username', serializer.validated_data)

    def test_id_is_read_only(self):
        serializer = UserProfileSerializer(
            instance=self.user,
            data={'id': 99999},
            partial=True,
            context=self._get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        self.assertNotIn('id', serializer.validated_data)

    def test_update_first_name(self):
        serializer = UserProfileSerializer(
            instance=self.user,
            data={'first_name': 'Updated'},
            partial=True,
            context=self._get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')


class ChangePasswordSerializerTestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory.create()

    def _get_serializer_context(self):
        request = RequestFactory().get('/')
        request.user = self.user
        return {'request': request}

    def test_valid_password_change(self):
        serializer = ChangePasswordSerializer(
            data={
                'current_password': 'passWord*123',
                'new_password': 'newPass*456',
            },
            context=self._get_serializer_context(),
        )
        self.assertTrue(serializer.is_valid())

    def test_wrong_current_password(self):
        serializer = ChangePasswordSerializer(
            data={
                'current_password': 'wrong-password',
                'new_password': 'newPass*456',
            },
            context=self._get_serializer_context(),
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('current_password', serializer.errors)

    def test_same_password(self):
        serializer = ChangePasswordSerializer(
            data={
                'current_password': 'passWord*123',
                'new_password': 'passWord*123',
            },
            context=self._get_serializer_context(),
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_new_password_too_short(self):
        serializer = ChangePasswordSerializer(
            data={
                'current_password': 'passWord*123',
                'new_password': 'short',
            },
            context=self._get_serializer_context(),
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('new_password', serializer.errors)
