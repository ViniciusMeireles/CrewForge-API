from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationProfilePermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.profile = self.organization.get_profile()
        self.list_url = reverse(viewname='accounts:organization_profiles-list')
        self.detail_url = reverse(
            viewname='accounts:organization_profiles-detail',
            args=[self.profile.id],
        )

    def test_not_authenticated_list(self):
        self.client.logout()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_retrieve(self):
        self.client.logout()
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_update(self):
        self.client.logout()
        response = self.client.put(
            self.detail_url, data={'website': 'https://test.com'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_delete(self):
        self.client.logout()
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_choices(self):
        self.client.logout()
        url = reverse(viewname='accounts:organization_profiles-choices')
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_active_member_retrieve(self):
        member = MemberFactory(
            organization=self.organization,
            is_active=False,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=member)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_update(self):
        member = MemberFactory(
            organization=self.organization,
            is_active=False,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=member)
        response = self.client.patch(
            self.detail_url,
            data={'website': 'https://test.com'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_delete(self):
        member = MemberFactory(
            organization=self.organization,
            is_active=False,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=member)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_list(self):
        member = MemberFactory(
            organization=self.organization,
            is_active=False,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_choices(self):
        member = MemberFactory(
            organization=self.organization,
            is_active=False,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=member)
        url = reverse(viewname='accounts:organization_profiles-choices')
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_owner_can_update(self):
        response = self.client.patch(
            self.detail_url,
            data={'website': 'https://owner-update.com'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_can_delete(self):
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_admin_can_update(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        response = self.client.patch(
            self.detail_url,
            data={'website': 'https://admin-update.com'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_delete(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_manager_cannot_update(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        response = self.client.patch(
            self.detail_url,
            data={'website': 'https://manager-update.com'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_delete(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_member_cannot_update(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        response = self.client.patch(
            self.detail_url,
            data={'website': 'https://member-update.com'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_member_cannot_delete(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_owner_can_retrieve(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_retrieve(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_manager_can_retrieve(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_member_can_retrieve(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_cross_org_member_retrieve(self):
        other_org = OrganizationFactory()
        other_member = other_org.owner
        self.client.force_authenticate(member=other_member)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_member_update(self):
        other_org = OrganizationFactory()
        other_admin = MemberFactory(
            organization=other_org, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=other_admin)
        response = self.client.patch(
            self.detail_url,
            data={'website': 'https://cross-org.com'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_member_delete(self):
        other_org = OrganizationFactory()
        other_admin = MemberFactory(
            organization=other_org, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=other_admin)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
