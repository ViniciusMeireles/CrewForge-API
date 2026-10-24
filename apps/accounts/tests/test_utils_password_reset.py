from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from apps.accounts.factories.users import UserFactory
from apps.accounts.utils.password_reset import password_reset_link

RESET_URL = 'http://app.test/auth/reset-password'


@override_settings(FRONTEND_RESET_URL=RESET_URL)
class PasswordResetLinkTestCase(TestCase):
    def test_link_carries_a_valid_uid_and_token(self):
        user = UserFactory()
        link = password_reset_link(user)
        self.assertTrue(link.startswith(f'{RESET_URL}?uid='))
        query = dict(part.split('=', 1) for part in link.split('?', 1)[1].split('&'))
        self.assertEqual(force_str(urlsafe_base64_decode(query['uid'])), str(user.pk))
        self.assertTrue(default_token_generator.check_token(user, query['token']))
