import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices, OrganizationImageTypeChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organization_image import OrganizationImageFactory
from apps.accounts.models.organization import OrganizationImage
from apps.accounts.tests.mixins import APITestCaseMixin


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OrganizationImageIntegrationTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.profile = self.organization.get_profile()
        self.list_url = reverse(viewname='accounts:organization_images-list')

    def _detail_url(self, image):
        return reverse(viewname='accounts:organization_images-detail', args=[image.id])

    def _payload(self, **overrides):
        payload = {
            'image.file': SimpleUploadedFile(
                name='logo.png',
                content=b'fake-png-content',
                content_type='image/png',
            ),
            'image_type': OrganizationImageTypeChoices.LOGO,
        }
        payload.update(overrides)
        return payload

    def test_full_crud_flow_owner(self):
        create_resp = self.client.post(
            self.list_url, data=self._payload(), format='multipart'
        )
        self.assertEqual(create_resp.status_code, http_status.HTTP_201_CREATED)
        image_id = create_resp.data['id']

        list_resp = self.client.get(self.list_url)
        self.assertEqual(list_resp.status_code, http_status.HTTP_200_OK)
        self.assertGreaterEqual(list_resp.data['count'], 1)

        detail_url = self._detail_url(OrganizationImage(id=image_id))
        retrieve_resp = self.client.get(detail_url)
        self.assertEqual(retrieve_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            retrieve_resp.data['image_type'], OrganizationImageTypeChoices.LOGO
        )

        put_payload = self._payload(image_type=OrganizationImageTypeChoices.COVER)
        put_resp = self.client.put(detail_url, data=put_payload, format='multipart')
        self.assertEqual(put_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            put_resp.data['image_type'], OrganizationImageTypeChoices.COVER
        )

        patch_resp = self.client.patch(
            detail_url,
            data={'image_type': OrganizationImageTypeChoices.FAVICON},
            format='multipart',
        )
        self.assertEqual(patch_resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            patch_resp.data['image_type'], OrganizationImageTypeChoices.FAVICON
        )

        delete_resp = self.client.delete(detail_url)
        self.assertEqual(delete_resp.status_code, http_status.HTTP_204_NO_CONTENT)

        list_after = self.client.get(self.list_url)
        for result in list_after.data['results']:
            self.assertNotEqual(result['id'], image_id)

    def test_full_crud_flow_admin(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)

        create_resp = self.client.post(
            self.list_url, data=self._payload(), format='multipart'
        )
        self.assertEqual(create_resp.status_code, http_status.HTTP_201_CREATED)
        image_id = create_resp.data['id']

        detail_url = self._detail_url(OrganizationImage(id=image_id))

        update_resp = self.client.patch(
            detail_url,
            data={'image_type': OrganizationImageTypeChoices.COVER},
            format='multipart',
        )
        self.assertEqual(update_resp.status_code, http_status.HTTP_200_OK)

        delete_resp = self.client.delete(detail_url)
        self.assertEqual(delete_resp.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_permission_hierarchy_write_access(self):
        type_sequence = [
            OrganizationImageTypeChoices.COVER,
            OrganizationImageTypeChoices.FAVICON,
            OrganizationImageTypeChoices.OG_IMAGE,
            OrganizationImageTypeChoices.LOGO_HORIZONTAL,
        ]
        roles_expected = [
            (self.organization.owner, http_status.HTTP_200_OK),
            (
                MemberFactory(
                    organization=self.organization, role=MemberRoleChoices.ADMIN
                ),
                http_status.HTTP_200_OK,
            ),
            (
                MemberFactory(
                    organization=self.organization, role=MemberRoleChoices.MANAGER
                ),
                http_status.HTTP_403_FORBIDDEN,
            ),
            (
                MemberFactory(
                    organization=self.organization, role=MemberRoleChoices.MEMBER
                ),
                http_status.HTTP_403_FORBIDDEN,
            ),
        ]

        for (member, expected_status), target_type in zip(
            roles_expected, type_sequence, strict=True
        ):
            with self.subTest(member=member.role):
                OrganizationImage.objects.filter(profile=self.profile).delete()
                image = OrganizationImageFactory(profile=self.profile)
                detail_url = self._detail_url(image)
                self.client.force_authenticate(member=member)
                response = self.client.patch(
                    detail_url,
                    data={'image_type': target_type},
                    format='multipart',
                )
                self.assertEqual(
                    response.status_code,
                    expected_status,
                    (
                        f'{member.role} expected {expected_status},'
                        f' got {response.status_code}'
                    ),
                )

    def test_permission_hierarchy_read_access(self):
        image = OrganizationImageFactory(profile=self.profile)
        detail_url = self._detail_url(image)

        roles = [
            self.organization.owner,
            MemberFactory(organization=self.organization, role=MemberRoleChoices.ADMIN),
            MemberFactory(
                organization=self.organization, role=MemberRoleChoices.MANAGER
            ),
            MemberFactory(
                organization=self.organization, role=MemberRoleChoices.MEMBER
            ),
        ]

        for member in roles:
            with self.subTest(member=member.role):
                self.client.force_authenticate(member=member)
                response = self.client.get(detail_url)
                self.assertEqual(
                    response.status_code,
                    http_status.HTTP_200_OK,
                    f'{member.role} expected 200, got {response.status_code}',
                )

    def test_create_then_choices_reflects(self):
        self.client.post(self.list_url, data=self._payload(), format='multipart')
        choices_resp = self.client.get(
            reverse(viewname='accounts:organization_images-choices')
        )
        self.assertEqual(choices_resp.status_code, http_status.HTTP_200_OK)
        self.assertGreaterEqual(choices_resp.data['count'], 1)
