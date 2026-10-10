from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import translation
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import PreferredLanguageChoices
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import DEFAULT_PASSWORD, UserFactory
from apps.accounts.models.user import User
from apps.accounts.serializers.member import (
    UserCreateWithInviteSerializer,
    UserUpdateSerializer,
)
from apps.accounts.serializers.signup import UserCreateSignupSerializer
from apps.accounts.serializers.user import UserReadySerializer, UserSerializer
from apps.accounts.serializers.user_profile import UserProfileSerializer
from apps.accounts.tests.mixins import APITestCaseMixin


class PreferredLanguageModelTestCase(TestCase):
    def setUp(self):
        self.field = User._meta.get_field('preferred_language')

    def test_default_is_english(self):
        self.assertEqual(UserFactory.create().preferred_language, 'en')

    def test_field_is_not_null_with_default(self):
        self.assertFalse(self.field.null)
        self.assertEqual(self.field.default, 'en')
        self.assertEqual(self.field.max_length, 8)

    def test_choices_values(self):
        self.assertEqual(
            {value for value, _ in PreferredLanguageChoices.choices},
            {'en', 'pt-br'},
        )

    def test_choices_labels_stay_native_under_portuguese(self):
        with translation.override('pt-br'):
            labels = dict(PreferredLanguageChoices.choices)
        self.assertEqual(labels, {'en': 'English', 'pt-br': 'Português (Brasil)'})

    def test_verbose_name_and_help_text_translated(self):
        with translation.override('pt-br'):
            self.assertEqual(str(self.field.verbose_name), 'Idioma preferido')
            self.assertEqual(
                str(self.field.help_text),
                'Idioma usado para renderizar os e-mails deste usuário.',
            )
        with translation.override('en'):
            self.assertEqual(str(self.field.verbose_name), 'Preferred Language')


class PreferredLanguageMigrationTestCase(TransactionTestCase):
    def test_existing_users_are_backfilled_to_english(self):
        user = UserFactory.create(preferred_language='pt-br')
        executor = MigrationExecutor(connection)
        try:
            executor.migrate([('accounts', '0004_user_email_verified_at')])
            executor.loader.build_graph()
            executor.migrate([('accounts', '0005_user_preferred_language')])
            user.refresh_from_db()
            self.assertEqual(user.preferred_language, 'en')
        finally:
            executor.loader.build_graph()
            executor.migrate([('accounts', '0005_user_preferred_language')])


class PreferredLanguageSignupTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse('accounts:signup-list')

    def _payload(self, **user_overrides):
        user = UserFactory.build()
        organization = OrganizationFactory.build()
        member = MemberFactory.build()
        payload = {
            'user': {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'password': DEFAULT_PASSWORD,
            },
            'organization': {
                'name': organization.name,
                'slug': organization.slug,
            },
            'nickname': member.nickname,
        }
        payload['user'].update(user_overrides)
        return payload

    def _created_user(self, response) -> User:
        return User.objects.get(pk=response.data['user']['id'])

    def test_signup_initializes_from_request_language(self):
        response = self.client.post(
            self.url,
            self._payload(),
            format='json',
            HTTP_ACCEPT_LANGUAGE='pt-BR',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(self._created_user(response).preferred_language, 'pt-br')

    def test_signup_defaults_to_english_without_header(self):
        response = self.client.post(self.url, self._payload(), format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(self._created_user(response).preferred_language, 'en')

    def test_signup_unsupported_language_defaults_to_english(self):
        response = self.client.post(
            self.url,
            self._payload(),
            format='json',
            HTTP_ACCEPT_LANGUAGE='fr-FR,fr;q=0.9',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(self._created_user(response).preferred_language, 'en')

    def test_signup_payload_cannot_set_preferred_language(self):
        response = self.client.post(
            self.url,
            self._payload(preferred_language='pt-br'),
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(self._created_user(response).preferred_language, 'en')


class PreferredLanguageCreateWithInviteTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()

    def _invitation(self):
        return InvitationFactory.create(
            organization=self.organization,
            email=UserFactory.build().email,
            expired_at=None,
        )

    def _payload(self, **user_overrides):
        user = UserFactory.build()
        payload = {
            'user': {
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'password': DEFAULT_PASSWORD,
            },
            'nickname': MemberFactory.build().nickname,
        }
        payload['user'].update(user_overrides)
        return payload

    def _post(self, invitation, payload, **extra):
        url = reverse('accounts:members-create-with-invite', args=[invitation.key])
        return self.client.post(url, data=payload, format='json', **extra)

    def test_create_with_invite_initializes_from_request_language(self):
        response = self._post(
            self._invitation(),
            self._payload(),
            HTTP_ACCEPT_LANGUAGE='pt-BR',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        user = User.objects.get(pk=response.data['user']['id'])
        self.assertEqual(user.preferred_language, 'pt-br')

    def test_create_with_invite_defaults_to_english(self):
        response = self._post(self._invitation(), self._payload())
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        user = User.objects.get(pk=response.data['user']['id'])
        self.assertEqual(user.preferred_language, 'en')

    def test_create_with_invite_payload_cannot_set_preferred_language(self):
        response = self._post(
            self._invitation(),
            self._payload(preferred_language='pt-br'),
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        user = User.objects.get(pk=response.data['user']['id'])
        self.assertEqual(user.preferred_language, 'en')


class PreferredLanguageExposureTestCase(APITestCaseMixin, APITestCase):
    def test_profile_serializer_exposes_field(self):
        self.assertIn('preferred_language', UserProfileSerializer().fields)

    def test_absent_from_user_serializers(self):
        for serializer_class in (
            UserSerializer,
            UserCreateSignupSerializer,
            UserCreateWithInviteSerializer,
            UserUpdateSerializer,
            UserReadySerializer,
        ):
            with self.subTest(serializer=serializer_class.__name__):
                self.assertNotIn('preferred_language', serializer_class().fields)

    def test_member_detail_does_not_expose_field(self):
        organization = self.new_account()
        member = MemberFactory.create(organization=organization)
        response = self.client.get(reverse('accounts:members-detail', args=[member.id]))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertNotIn('preferred_language', response.data['user'])

    def test_member_update_cannot_set_field(self):
        organization = self.new_account()
        member = MemberFactory.create(organization=organization)
        response = self.client.patch(
            reverse('accounts:members-detail', args=[member.id]),
            data={'user': {'preferred_language': 'pt-br'}},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        member.user.refresh_from_db()
        self.assertEqual(member.user.preferred_language, 'en')
