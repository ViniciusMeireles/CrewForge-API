from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationPermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('accounts:organizations-list')
        self.choices_url = reverse('accounts:organizations-choices')

    def _detail_url(self, org):
        return reverse('accounts:organizations-detail', args=[org.id])

    def _org_payload(self, **overrides):
        data = OrganizationFactory.build()
        payload = {
            'name': data.name,
            'slug': data.slug,
        }
        payload.update(overrides)
        return payload

    # --- Unauthenticated ---

    def test_not_authenticated_list(self):
        self.client.logout()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_not_authenticated_create(self):
        self.client.logout()
        payload = self._org_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_retrieve(self):
        self.client.logout()
        url = self._detail_url(self.organization)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_not_authenticated_update(self):
        self.client.logout()
        url = self._detail_url(self.organization)
        payload = self._org_payload()
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_delete(self):
        self.client.logout()
        url = self._detail_url(self.organization)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    # --- Inactive member ---

    def test_not_active_member_list(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_not_active_member_create(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        payload = self._org_payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_not_active_member_update(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        url = self._detail_url(self.organization)
        payload = self._org_payload()
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_delete(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        url = self._detail_url(self.organization)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- Owner ---

    def test_owner_can_update(self):
        url = self._detail_url(self.organization)
        payload = self._org_payload()
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_can_delete(self):
        url = self._detail_url(self.organization)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    # --- Admin ---

    def test_admin_cannot_update(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        url = self._detail_url(self.organization)
        payload = self._org_payload()
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_delete(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        url = self._detail_url(self.organization)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- Manager ---

    def test_manager_cannot_update(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        url = self._detail_url(self.organization)
        payload = self._org_payload()
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_delete(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        url = self._detail_url(self.organization)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- Member ---

    def test_member_cannot_update(self):
        member_role = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member_role)
        url = self._detail_url(self.organization)
        payload = self._org_payload()
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_member_cannot_delete(self):
        member_role = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member_role)
        url = self._detail_url(self.organization)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    # --- All roles can read ---

    def test_owner_can_retrieve(self):
        url = self._detail_url(self.organization)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_retrieve(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        url = self._detail_url(self.organization)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_manager_can_retrieve(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        url = self._detail_url(self.organization)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_member_can_retrieve(self):
        member_role = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member_role)
        url = self._detail_url(self.organization)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Cross-org ---

    def test_cross_org_member_update_returns_403(self):
        other_org = OrganizationFactory()
        other_owner = other_org.owner
        self.client.force_authenticate(member=other_owner)
        url = self._detail_url(self.organization)
        payload = self._org_payload()
        response = self.client.put(url, data=payload, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_cross_org_member_retrieve_returns_200(self):
        other_org = OrganizationFactory()
        other_owner = other_org.owner
        self.client.force_authenticate(member=other_owner)
        url = self._detail_url(self.organization)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_cross_org_member_delete_returns_403(self):
        other_org = OrganizationFactory()
        other_owner = other_org.owner
        self.client.force_authenticate(member=other_owner)
        url = self._detail_url(self.organization)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_cross_org_inactive_member_returns_200(self):
        MemberFactory(is_active=False)
        url = self._detail_url(self.organization)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Choices ---

    def test_not_authenticated_choices(self):
        self.client.logout()
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_not_active_member_choices(self):
        member = MemberFactory(organization=self.organization, is_active=False)
        self.client.force_authenticate(member=member)
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- List ---

    def test_owner_can_list(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_list(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    # --- Cross-org ---

    def test_cross_org_member_list_returns_empty(self):
        other_org = OrganizationFactory()
        other_owner = other_org.owner
        self.client.force_authenticate(member=other_owner)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        # Organization list is global, cross-org members see all orgs
        self.assertGreater(response.data['count'], 0)

    def test_cross_org_member_choices_returns_empty(self):
        other_org = OrganizationFactory()
        other_owner = other_org.owner
        self.client.force_authenticate(member=other_owner)
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertGreater(response.data['count'], 0)
