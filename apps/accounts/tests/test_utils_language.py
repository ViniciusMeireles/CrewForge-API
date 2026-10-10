from django.test import TestCase
from django.utils import translation

from apps.accounts.factories.users import UserFactory
from apps.accounts.utils.language import (
    current_language,
    normalize_language,
    resolve_invitation_language,
    resolve_recipient_language,
)


class NormalizeLanguageTestCase(TestCase):
    def test_normalizes_supported_values(self):
        cases = {
            'pt': 'pt-br',
            'pt-br': 'pt-br',
            'PT-BR': 'pt-br',
            'en': 'en',
            'en-us': 'en',
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(normalize_language(value), expected)

    def test_falls_back_to_english(self):
        for value in (None, '', 'fr-FR', 'es'):
            with self.subTest(value=value):
                self.assertEqual(normalize_language(value), 'en')


class CurrentLanguageTestCase(TestCase):
    def test_returns_active_language(self):
        with translation.override('pt-br'):
            self.assertEqual(current_language(), 'pt-br')

    def test_defaults_to_english_outside_request(self):
        self.assertEqual(current_language(), 'en')


class ResolveRecipientLanguageTestCase(TestCase):
    def test_no_user_falls_back_to_current_language(self):
        self.assertEqual(resolve_recipient_language(None), 'en')
        with translation.override('pt-br'):
            self.assertEqual(resolve_recipient_language(None), 'pt-br')

    def test_user_preference_wins_over_active_language(self):
        user = UserFactory.create(preferred_language='pt-br')
        with translation.override('en'):
            self.assertEqual(resolve_recipient_language(user), 'pt-br')

    def test_user_preference_english_wins_over_portuguese_request(self):
        user = UserFactory.create(preferred_language='en')
        with translation.override('pt-br'):
            self.assertEqual(resolve_recipient_language(user), 'en')

    def test_user_without_request_uses_preference(self):
        user = UserFactory.create(preferred_language='pt-br')
        self.assertEqual(resolve_recipient_language(user), 'pt-br')


class ResolveInvitationLanguageTestCase(TestCase):
    def test_invitee_preference_is_case_insensitive(self):
        UserFactory.create(email='jane@example.com', preferred_language='pt-br')
        self.assertEqual(resolve_invitation_language('Jane@Example.com'), 'pt-br')

    def test_invitee_preference_wins_over_request_language(self):
        UserFactory.create(email='jane@example.com', preferred_language='pt-br')
        with translation.override('en'):
            self.assertEqual(resolve_invitation_language('jane@example.com'), 'pt-br')

    def test_no_user_falls_back_to_current_language(self):
        with translation.override('pt-br'):
            self.assertEqual(resolve_invitation_language('nobody@example.com'), 'pt-br')
        self.assertEqual(resolve_invitation_language('nobody@example.com'), 'en')
