import tempfile

from django.test import override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organization_image import OrganizationImageFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OrganizationImagePermissionTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.profile = self.organization.get_profile()
        self.owner_user = self.organization.owner.user
        self.owner_member = self.organization.owner
        self.list_url = reverse(viewname='accounts:organization_images-list')

    def _detail_url(self, image):
        return reverse(viewname='accounts:organization_images-detail', args=[image.id])

    def _create_image(self):
        image = OrganizationImageFactory(
            profile=self.profile,
        )
        return image

    def test_not_authenticated_list(self):
        self.client.logout()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_not_authenticated_retrieve(self):
        image = self._create_image()
        self.client.logout()
        url = self._detail_url(image)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_not_authenticated_create(self):
        self.client.logout()
        response = self.client.post(self.list_url, data={}, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_update(self):
        image = self._create_image()
        self.client.logout()
        url = self._detail_url(image)
        response = self.client.put(
            url, data={'image_type': 'cover'}, format='multipart'
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_delete(self):
        image = self._create_image()
        self.client.logout()
        url = self._detail_url(image)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_not_authenticated_choices(self):
        self.client.logout()
        url = reverse(viewname='accounts:organization_images-choices')
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_not_active_member_create(self):
        member = MemberFactory(
            organization=self.organization,
            is_active=False,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=member)
        response = self.client.post(self.list_url, data={}, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_update(self):
        image = self._create_image()
        member = MemberFactory(
            organization=self.organization,
            is_active=False,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=member)
        url = self._detail_url(image)
        response = self.client.patch(
            url, data={'image_type': 'cover'}, format='multipart'
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_delete(self):
        image = self._create_image()
        member = MemberFactory(
            organization=self.organization,
            is_active=False,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=member)
        url = self._detail_url(image)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_not_active_member_retrieve(self):
        image = self._create_image()
        member = MemberFactory(
            organization=self.organization,
            is_active=False,
            role=MemberRoleChoices.ADMIN,
        )
        self.client.force_authenticate(member=member)
        url = self._detail_url(image)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_can_update(self):
        image = self._create_image()
        url = self._detail_url(image)
        response = self.client.patch(
            url, data={'image_type': 'cover'}, format='multipart'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_owner_can_delete(self):
        image = self._create_image()
        url = self._detail_url(image)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_admin_can_update(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        image = self._create_image()
        url = self._detail_url(image)
        response = self.client.patch(
            url, data={'image_type': 'cover'}, format='multipart'
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_delete(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        image = self._create_image()
        url = self._detail_url(image)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_manager_cannot_update(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        image = self._create_image()
        url = self._detail_url(image)
        response = self.client.patch(
            url, data={'image_type': 'cover'}, format='multipart'
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_delete(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        image = self._create_image()
        url = self._detail_url(image)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_member_cannot_update(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        image = self._create_image()
        url = self._detail_url(image)
        response = self.client.patch(
            url, data={'image_type': 'cover'}, format='multipart'
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_member_cannot_delete(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        image = self._create_image()
        url = self._detail_url(image)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_owner_can_retrieve(self):
        image = self._create_image()
        url = self._detail_url(image)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_can_retrieve(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        image = self._create_image()
        url = self._detail_url(image)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_manager_can_retrieve(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        image = self._create_image()
        url = self._detail_url(image)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_member_can_retrieve(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        self.client.force_authenticate(member=member)
        image = self._create_image()
        url = self._detail_url(image)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_cross_org_member_retrieve(self):
        other_org = OrganizationFactory()
        other_member = other_org.owner
        image = self._create_image()
        self.client.force_authenticate(member=other_member)
        url = self._detail_url(image)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_cross_org_member_update(self):
        other_org = OrganizationFactory()
        other_admin = MemberFactory(
            organization=other_org, role=MemberRoleChoices.ADMIN
        )
        image = self._create_image()
        self.client.force_authenticate(member=other_admin)
        url = self._detail_url(image)
        response = self.client.patch(
            url, data={'image_type': 'cover'}, format='multipart'
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_cross_org_member_delete(self):
        other_org = OrganizationFactory()
        other_admin = MemberFactory(
            organization=other_org, role=MemberRoleChoices.ADMIN
        )
        image = self._create_image()
        self.client.force_authenticate(member=other_admin)
        url = self._detail_url(image)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
