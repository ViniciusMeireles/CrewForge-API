from django.urls import NoReverseMatch, reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin, FilterOptionsTestMixin

OK = http_status.HTTP_200_OK
UNAUTHORIZED = http_status.HTTP_401_UNAUTHORIZED
FORBIDDEN = http_status.HTTP_403_FORBIDDEN

RESOURCES = {
    'invitations': {'role', 'role__in', 'order_by'},
    'members': {'organization', 'user', 'role', 'role__in', 'order_by'},
    'organization_images': {'image_type', 'organization', 'order_by'},
    'organizations': {'order_by'},
    'organization_profiles': {'order_by'},
}


def _status(**overrides):
    return {resource: overrides.get(resource, OK) for resource in RESOURCES}


class AccountsFilterOptionsTestMixin(FilterOptionsTestMixin):
    filter_options_namespace = 'accounts'
    expected_status = {
        'owner': _status(),
        'member': _status(invitations=FORBIDDEN),
        'inactive': _status(
            invitations=FORBIDDEN, members=FORBIDDEN, organization_profiles=FORBIDDEN
        ),
        'no_session': _status(
            invitations=FORBIDDEN, members=FORBIDDEN, organization_profiles=FORBIDDEN
        ),
        'anonymous': _status(
            invitations=UNAUTHORIZED,
            members=UNAUTHORIZED,
            organization_profiles=UNAUTHORIZED,
        ),
    }


class FilterOptionsPermissionTestCase(
    AccountsFilterOptionsTestMixin, APITestCaseMixin, APITestCase
):
    def setUp(self):
        self.organization = self.new_account()

    def test_owner(self):
        self.assert_expected_status('owner')

    def test_member_role(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        self.assert_expected_status('member')

    def test_inactive_member(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        self.assert_expected_status('inactive')

    def test_without_organization_session(self):
        self.client.logout()
        self.client.force_authenticate(user=self.organization.owner.user)
        self.assert_expected_status('no_session')

    def test_not_authenticated(self):
        self.client.logout()
        self.assert_expected_status('anonymous')


class FilterOptionsContentTestCase(
    AccountsFilterOptionsTestMixin, APITestCaseMixin, APITestCase
):
    def setUp(self):
        self.organization = self.new_account()
        self.other_organization = OrganizationFactory()

    def test_fields(self):
        for resource, fields in RESOURCES.items():
            with self.subTest(resource=resource):
                response = self.client.get(self.filter_options_url(resource))
                self.assertEqual(set(response.data), fields)

    def test_role_choices(self):
        response = self.client.get(self.filter_options_url('invitations'))
        expected = set(MemberRoleChoices.values)
        self.assertEqual(self.option_values(response, 'role'), expected)
        self.assertEqual(self.option_values(response, 'role__in'), expected)

    def test_order_by_has_ascending_and_descending(self):
        response = self.client.get(
            self.filter_options_url('invitations'), {'order_by': ''}
        )
        values = self.option_values(response, 'order_by')
        self.assertIn('email', values)
        self.assertIn('-email', values)

    def test_field_selection(self):
        response = self.client.get(self.filter_options_url('members'), {'role': ''})
        self.assertEqual(set(response.data), {'role'})

    def test_members_scoped_to_organization(self):
        member = MemberFactory(organization=self.organization)
        inactive_user = UserFactory(is_active=False)
        MemberFactory(organization=self.organization, user=inactive_user)
        former_member = MemberFactory(organization=self.organization, is_active=False)
        MemberFactory(organization=self.other_organization, user=former_member.user)
        response = self.client.get(self.filter_options_url('members'))
        self.assertEqual(
            self.option_values(response, 'organization'), {self.organization.pk}
        )
        self.assertEqual(
            self.option_values(response, 'user'),
            {self.organization.owner.user_id, member.user_id},
        )

    def test_members_user_search(self):
        user = UserFactory(first_name='Zéfiro', last_name='Ünico')
        MemberFactory(organization=self.organization, user=user)
        response = self.client.get(
            self.filter_options_url('members'), {'user': 'zefiro unico'}
        )
        self.assertEqual(self.option_values(response, 'user'), {user.pk})

    def test_organization_images_scoped_to_organization(self):
        response = self.client.get(self.filter_options_url('organization_images'))
        self.assertEqual(
            self.option_values(response, 'organization'), {self.organization.pk}
        )

    def test_anonymous_relation_options_are_empty(self):
        self.client.logout()
        response = self.client.get(self.filter_options_url('organization_images'))
        self.assertEqual(response.status_code, OK)
        self.assertEqual(response.data['organization']['count'], 0)

    def test_stored_files_has_no_filter_options(self):
        with self.assertRaises(NoReverseMatch):
            reverse('accounts:stored_files-filter-options')
