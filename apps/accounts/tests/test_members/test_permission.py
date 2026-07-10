from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class MemberPermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:members-list')
        self.choices_url = reverse('accounts:members-choices')
        self.update_role_url_name = 'accounts:members-update-role'

    def _detail_url(self, member):
        return reverse('accounts:members-detail', args=[member.id])

    def _update_role_url(self, member):
        return reverse(self.update_role_url_name, args=[member.id])

    def _create_target_member(self, role=MemberRoleChoices.MEMBER):
        return MemberFactory(
            organization=self.organization,
            role=role,
        )

    # --- Unauthenticated ---

    def test_not_authenticated_list(self):
        self.client.logout()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_retrieve(self):
        member = self._create_target_member()
        self.client.logout()
        url = self._detail_url(member)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_update(self):
        member = self._create_target_member()
        self.client.logout()
        url = self._detail_url(member)
        response = self.client.patch(url, data={'nickname': 'new'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_delete(self):
        member = self._create_target_member()
        self.client.logout()
        url = self._detail_url(member)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_update_role(self):
        member = self._create_target_member()
        self.client.logout()
        url = reverse(self.update_role_url_name, args=[member.id])
        response = self.client.patch(url, data={'role': 'admin'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    # --- Inactive member ---

    def test_not_active_member_list(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_retrieve(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        url = self._detail_url(member)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_update(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        url = self._detail_url(member)
        response = self.client.patch(url, data={'nickname': 'new'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_delete(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        url = self._detail_url(member)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_update_role(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        target = self._create_target_member()
        url = reverse(self.update_role_url_name, args=[target.id])
        response = self.client.patch(url, data={'role': 'admin'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- Owner ---

    def test_owner_can_update(self):
        member = self._create_target_member()
        self.client.force_authenticate(member=self.organization.owner)
        url = self._detail_url(member)
        response = self.client.patch(
            url, data={'nickname': 'owner_updated'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_can_delete(self):
        member = self._create_target_member()
        self.client.force_authenticate(member=self.organization.owner)
        url = self._detail_url(member)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    # --- Admin ---

    def test_admin_can_update(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        member = self._create_target_member()
        url = self._detail_url(member)
        response = self.client.patch(
            url, data={'nickname': 'admin_updated'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_delete(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        member = self._create_target_member()
        url = self._detail_url(member)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    # --- Manager ---

    def test_manager_cannot_update_other(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        member = self._create_target_member()
        url = self._detail_url(member)
        response = self.client.patch(
            url, data={'nickname': 'manager_updated'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_delete(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        member = self._create_target_member()
        url = self._detail_url(member)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_manager_can_update_self(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        url = self._detail_url(manager)
        response = self.client.patch(
            url, data={'nickname': 'self_updated'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Member ---

    def test_member_cannot_update_other(self):
        member_role = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member_role)
        other = self._create_target_member()
        url = self._detail_url(other)
        response = self.client.patch(
            url, data={'nickname': 'member_updated'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_member_cannot_delete(self):
        member_role = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member_role)
        other = self._create_target_member()
        url = self._detail_url(other)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_member_can_update_self(self):
        member_role = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member_role)
        url = self._detail_url(member_role)
        response = self.client.patch(
            url, data={'nickname': 'self_updated'}, format='json'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Choices ---

    def test_not_authenticated_choices(self):
        self.client.logout()
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_active_member_choices(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- Owner list ---

    def test_owner_can_list(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Admin list ---

    def test_admin_can_list(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Role update permissions ---

    def test_owner_can_update_role_self(self):
        self.client.force_authenticate(member=self.organization.owner)
        url = reverse(self.update_role_url_name, args=[self.organization.owner.id])
        payload = {'role': MemberRoleChoices.ADMIN}
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_admin_can_update_role_lower(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        target = self._create_target_member()
        payload = {'role': MemberRoleChoices.MANAGER}
        url = self._update_role_url(target)
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_cannot_update_role_to_owner(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        target = self._create_target_member()
        payload = {'role': MemberRoleChoices.OWNER}
        url = self._update_role_url(target)
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    # --- All roles can read ---

    def test_owner_can_retrieve(self):
        member = self._create_target_member()
        url = self._detail_url(member)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_retrieve(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        member = self._create_target_member()
        url = self._detail_url(member)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_manager_can_retrieve(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        member = self._create_target_member()
        url = self._detail_url(member)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_member_can_retrieve(self):
        member_role = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member_role)
        other = self._create_target_member()
        url = self._detail_url(other)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Cross-org ---

    def test_cross_org_member_list_returns_empty(self):
        member = self._create_target_member()
        other_member = MemberFactory()
        self.client.force_authenticate(member=other_member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertNotEqual(result['id'], member.id)

    def test_cross_org_member_choices_returns_empty(self):
        member = self._create_target_member()
        other_member = MemberFactory()
        self.client.force_authenticate(member=other_member)
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertNotEqual(int(result['value']), member.id)

    def test_cross_org_member_retrieve_returns_404(self):
        other_org = OrganizationFactory()
        other_member = other_org.owner
        member = self._create_target_member()
        self.client.force_authenticate(member=other_member)
        url = self._detail_url(member)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_member_update_returns_404(self):
        other_org = OrganizationFactory()
        other_admin = MemberFactory(
            organization=other_org, role=MemberRoleChoices.ADMIN
        )
        member = self._create_target_member()
        self.client.force_authenticate(member=other_admin)
        url = self._detail_url(member)
        response = self.client.patch(url, data={'nickname': 'cross'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_cross_org_inactive_member_returns_404(self):
        inactive_member = MemberFactory(is_active=False)
        url = self._detail_url(inactive_member)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
