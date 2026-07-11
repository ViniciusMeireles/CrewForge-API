from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.accounts.serializers.signup import SignupSerializer

User = get_user_model()


class SignupModelTestCase(TestCase):
    def _valid_payload(self):
        user_data = UserFactory.build()
        org_data = OrganizationFactory.build()
        member_data = MemberFactory.build()
        return {
            'user': {
                'username': user_data.username,
                'email': user_data.email,
                'first_name': user_data.first_name,
                'last_name': user_data.last_name,
                'password': user_data.password,
            },
            'organization': {
                'name': org_data.name,
                'slug': org_data.slug,
            },
            'nickname': member_data.nickname,
        }

    def test_signup_creates_user(self):
        payload = self._valid_payload()
        serializer = SignupSerializer(data=payload, context={})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        user = instance.user
        self.assertEqual(user.username, payload['user']['username'])
        self.assertEqual(user.email, payload['user']['email'])
        self.assertEqual(user.first_name, payload['user']['first_name'])
        self.assertEqual(user.last_name, payload['user']['last_name'])

    def test_signup_creates_organization(self):
        payload = self._valid_payload()
        serializer = SignupSerializer(data=payload, context={})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        org = instance.organization
        self.assertEqual(org.name, payload['organization']['name'])
        self.assertEqual(org.slug, payload['organization']['slug'])

    def test_signup_creates_member_with_owner_role(self):
        payload = self._valid_payload()
        serializer = SignupSerializer(data=payload, context={})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        self.assertEqual(instance.role, MemberRoleChoices.OWNER)
        self.assertTrue(instance.is_owner)

    def test_signup_password_is_hashed(self):
        payload = self._valid_payload()
        raw_password = payload['user']['password']
        serializer = SignupSerializer(data=payload, context={})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        user = instance.user
        self.assertIsNotNone(user.password)
        self.assertNotEqual(user.password, raw_password)
        self.assertTrue(user.check_password(raw_password))

    def test_signup_creates_owner_link_on_organization(self):
        payload = self._valid_payload()
        serializer = SignupSerializer(data=payload, context={})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        org = instance.organization
        org.refresh_from_db()
        self.assertEqual(org.owner, instance)

    def test_signup_creates_user_organization_and_member(self):
        payload = self._valid_payload()
        serializer = SignupSerializer(data=payload, context={})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        user_qs = User.objects.filter(username=payload['user']['username'])
        self.assertTrue(user_qs.exists())

        org_qs = Organization.objects.filter(slug=payload['organization']['slug'])
        self.assertTrue(org_qs.exists())

        member_qs = Member.objects.filter(
            user=instance.user,
            organization=instance.organization,
        )
        self.assertTrue(member_qs.exists())

    def test_signup_cannot_set_custom_role(self):
        payload = self._valid_payload()
        payload['role'] = MemberRoleChoices.MEMBER
        serializer = SignupSerializer(data=payload, context={})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        self.assertEqual(instance.role, MemberRoleChoices.OWNER)
