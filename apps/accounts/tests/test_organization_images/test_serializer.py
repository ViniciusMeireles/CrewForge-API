import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import OrganizationImageTypeChoices, StoredFileAccess
from apps.accounts.factories.organization_image import OrganizationImageFactory
from apps.accounts.models.organization import OrganizationImage
from apps.accounts.tests.mixins import APITestCaseMixin


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OrganizationImageSerializerTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse(viewname='accounts:organization_images-list')
        self.owner_user = self.organization.owner.user

    def _image_payload(self, **overrides):
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

    def test_create_serializer_fields(self):
        payload = self._image_payload()
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('image_type', response.data)
        self.assertIn('image', response.data)
        self.assertIsInstance(response.data['image'], dict)

    def test_list_serializer_fields(self):
        OrganizationImageFactory(
            profile=self.organization.get_profile(),
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        result = response.data['results'][0]
        expected_fields = {'id', 'image_type', 'image'}
        self.assertEqual(set(result.keys()), expected_fields)
        self.assertIn('uuid', result['image'])
        self.assertIn('file_url', result['image'])
        self.assertIn('download_name', result['image'])
        self.assertIn('original_name', result['image'])
        self.assertIn('content_type', result['image'])
        self.assertIn('size', result['image'])

    def test_detail_serializer_fields(self):
        image = OrganizationImageFactory(
            profile=self.organization.get_profile(),
        )
        url = reverse(viewname='accounts:organization_images-detail', args=[image.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        expected_fields = {'id', 'image_type', 'image'}
        self.assertEqual(set(response.data.keys()), expected_fields)

    def test_read_only_fields_ignored_on_create(self):
        payload = self._image_payload(
            id=9999,
            is_active=False,
        )
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertNotEqual(response.data['id'], 9999)

    def test_validate_image_type_duplicate(self):
        profile = self.organization.get_profile()
        OrganizationImageFactory(
            profile=profile, image_type=OrganizationImageTypeChoices.LOGO
        )
        payload = self._image_payload(image_type=OrganizationImageTypeChoices.LOGO)
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('image_type', str(response.data))

    def test_validate_image_type_different_profile(self):
        OrganizationImageFactory(image_type=OrganizationImageTypeChoices.LOGO)
        payload = self._image_payload(image_type=OrganizationImageTypeChoices.LOGO)
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_create_sets_stored_file_permissions(self):
        payload = self._image_payload()
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        image = OrganizationImage.objects.get(id=response.data['id'])
        self.assertEqual(image.image.viewing_permission, StoredFileAccess.PUBLIC)
        self.assertEqual(
            image.image.updating_permission, StoredFileAccess.ADMINS_ORGANIZATION
        )

    def test_create_sets_stored_file_organization(self):
        payload = self._image_payload()
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        image = OrganizationImage.objects.get(id=response.data['id'])
        self.assertEqual(image.image.organization_id, self.organization.id)

    def test_create_sets_stored_file_owner(self):
        payload = self._image_payload()
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        image = OrganizationImage.objects.get(id=response.data['id'])
        self.assertEqual(image.image.owner_id, self.owner_user.id)

    def test_create_without_image_file(self):
        payload = {'image_type': OrganizationImageTypeChoices.LOGO}
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_with_all_image_types(self):
        for image_type in OrganizationImageTypeChoices.values:
            payload = self._image_payload(image_type=image_type)
            OrganizationImage.objects.filter(
                profile=self.organization.get_profile()
            ).delete()
            response = self.client.post(self.list_url, data=payload, format='multipart')
            self.assertEqual(
                response.status_code,
                http_status.HTTP_201_CREATED,
                f'Failed for image_type={image_type}',
            )

    def test_partial_update_image_type_only(self):
        image = OrganizationImageFactory(
            profile=self.organization.get_profile(),
        )
        url = reverse(viewname='accounts:organization_images-detail', args=[image.id])
        payload = {'image_type': OrganizationImageTypeChoices.COVER}
        response = self.client.patch(url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        image.refresh_from_db()
        self.assertEqual(image.image_type, OrganizationImageTypeChoices.COVER)

    def test_partial_update_image_file_only(self):
        image = OrganizationImageFactory(
            profile=self.organization.get_profile(),
        )
        old_uuid = image.image.uuid
        url = reverse(viewname='accounts:organization_images-detail', args=[image.id])
        payload = {
            'image.file': SimpleUploadedFile(
                name='new_logo.png',
                content=b'new-content',
                content_type='image/png',
            ),
        }
        response = self.client.patch(url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        image.refresh_from_db()
        self.assertEqual(image.image.uuid, old_uuid)
        self.assertEqual(image.image.file.read(), b'new-content')

    def test_partial_update_both_fields(self):
        image = OrganizationImageFactory(
            profile=self.organization.get_profile(),
        )
        url = reverse(viewname='accounts:organization_images-detail', args=[image.id])
        payload = {
            'image_type': OrganizationImageTypeChoices.COVER,
            'image.file': SimpleUploadedFile(
                name='cover.png',
                content=b'cover-content',
                content_type='image/png',
            ),
        }
        response = self.client.patch(url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        image.refresh_from_db()
        self.assertEqual(image.image_type, OrganizationImageTypeChoices.COVER)

    def test_full_update(self):
        image = OrganizationImageFactory(
            profile=self.organization.get_profile(),
        )
        url = reverse(viewname='accounts:organization_images-detail', args=[image.id])
        payload = {
            'image_type': OrganizationImageTypeChoices.COVER,
            'image.file': SimpleUploadedFile(
                name='cover.png',
                content=b'cover-content',
                content_type='image/png',
            ),
        }
        response = self.client.put(url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        image.refresh_from_db()
        self.assertEqual(image.image_type, OrganizationImageTypeChoices.COVER)

    def test_update_duplicate_image_type(self):
        profile = self.organization.get_profile()
        OrganizationImageFactory(
            profile=profile, image_type=OrganizationImageTypeChoices.LOGO
        )
        image2 = OrganizationImageFactory(
            profile=profile, image_type=OrganizationImageTypeChoices.COVER
        )
        url = reverse(viewname='accounts:organization_images-detail', args=[image2.id])
        payload = {'image_type': OrganizationImageTypeChoices.LOGO}
        response = self.client.patch(url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_update_nonexistent(self):
        url = reverse(viewname='accounts:organization_images-detail', args=[99999])
        payload = {'image_type': OrganizationImageTypeChoices.COVER}
        response = self.client.patch(url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_validate_sets_profile_from_auth(self):
        payload = self._image_payload()
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        image = OrganizationImage.objects.get(id=response.data['id'])
        self.assertEqual(image.profile_id, self.organization.get_profile().id)

    def test_created_by_updated_by_on_create(self):
        payload = self._image_payload()
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        image = OrganizationImage.objects.get(id=response.data['id'])
        self.assertEqual(image.created_by_id, self.owner_user.id)
        self.assertEqual(image.updated_by_id, self.owner_user.id)
