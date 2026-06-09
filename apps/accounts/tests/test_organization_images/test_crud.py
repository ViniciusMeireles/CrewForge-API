import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import OrganizationImageTypeChoices
from apps.accounts.factories.organization_image import OrganizationImageFactory
from apps.accounts.models.organization import OrganizationImage
from apps.accounts.tests.mixins import APITestCaseMixin


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OrganizationImageCRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.profile = self.organization.get_profile()
        self.list_url = reverse(viewname='accounts:organization_images-list')
        self.choices_url = reverse(viewname='accounts:organization_images-choices')

    def _detail_url(self, image):
        return reverse(viewname='accounts:organization_images-detail', args=[image.id])

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

    def test_list_images(self):
        OrganizationImageFactory(
            profile=self.profile, image_type=OrganizationImageTypeChoices.LOGO
        )
        OrganizationImageFactory(
            profile=self.profile, image_type=OrganizationImageTypeChoices.COVER
        )
        OrganizationImageFactory(
            profile=self.profile, image_type=OrganizationImageTypeChoices.FAVICON
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 3)

    def test_list_only_active(self):
        OrganizationImageFactory(
            profile=self.profile, image_type=OrganizationImageTypeChoices.LOGO
        )
        OrganizationImageFactory(
            profile=self.profile, image_type=OrganizationImageTypeChoices.COVER
        )
        OrganizationImageFactory(
            profile=self.profile, image_type=OrganizationImageTypeChoices.FAVICON
        )
        OrganizationImageFactory(
            profile=self.profile,
            image_type=OrganizationImageTypeChoices.OG_IMAGE,
            is_active=False,
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)

    def test_create_image(self):
        payload = self._image_payload()
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['image_type'], OrganizationImageTypeChoices.LOGO)
        self.assertIsInstance(response.data['image'], dict)
        self.assertIn('uuid', response.data['image'])

    def test_create_image_default_type(self):
        payload = {
            'image.file': SimpleUploadedFile(
                name='logo.png',
                content=b'fake-png-content',
                content_type='image/png',
            ),
        }
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['image_type'], OrganizationImageTypeChoices.LOGO)

    def test_retrieve_image(self):
        image = OrganizationImageFactory(profile=self.profile)
        url = self._detail_url(image)
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['id'], image.id)
        self.assertEqual(response.data['image_type'], image.image_type)

    def test_retrieve_nonexistent(self):
        url = reverse(viewname='accounts:organization_images-detail', args=[99999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_update_image_full(self):
        image = OrganizationImageFactory(profile=self.profile)
        url = self._detail_url(image)
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

    def test_partial_update_image_type(self):
        image = OrganizationImageFactory(profile=self.profile)
        url = self._detail_url(image)
        response = self.client.patch(
            url,
            data={'image_type': OrganizationImageTypeChoices.COVER},
            format='multipart',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        image.refresh_from_db()
        self.assertEqual(image.image_type, OrganizationImageTypeChoices.COVER)

    def test_partial_update_image_file(self):
        image = OrganizationImageFactory(profile=self.profile)
        old_uuid = image.image.uuid
        url = self._detail_url(image)
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

    def test_delete_image(self):
        image = OrganizationImageFactory(profile=self.profile)
        url = self._detail_url(image)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_delete_soft_delete(self):
        image = OrganizationImageFactory(profile=self.profile)
        url = self._detail_url(image)
        self.client.delete(url)
        image.refresh_from_db()
        self.assertFalse(image.is_active)

    def test_delete_removes_from_list(self):
        image = OrganizationImageFactory(profile=self.profile)
        url = self._detail_url(image)
        self.client.delete(url)
        response = self.client.get(self.list_url)
        for result in response.data['results']:
            self.assertNotEqual(result['id'], image.id)

    def test_delete_nonexistent(self):
        url = reverse(viewname='accounts:organization_images-detail', args=[99999])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_create_duplicate_image_type_same_profile(self):
        OrganizationImageFactory(
            profile=self.profile, image_type=OrganizationImageTypeChoices.LOGO
        )
        payload = self._image_payload(image_type=OrganizationImageTypeChoices.LOGO)
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_create_different_image_type_same_profile(self):
        OrganizationImageFactory(
            profile=self.profile, image_type=OrganizationImageTypeChoices.LOGO
        )
        payload = self._image_payload(image_type=OrganizationImageTypeChoices.COVER)
        response = self.client.post(self.list_url, data=payload, format='multipart')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_create_all_image_types(self):
        for image_type in OrganizationImageTypeChoices.values:
            OrganizationImage.objects.filter(profile=self.profile).delete()
            payload = self._image_payload(image_type=image_type)
            response = self.client.post(self.list_url, data=payload, format='multipart')
            self.assertEqual(
                response.status_code,
                http_status.HTTP_201_CREATED,
                f'Failed for image_type={image_type}',
            )
            self.assertEqual(response.data['image_type'], image_type)

    def test_choices_endpoint(self):
        OrganizationImageFactory(
            profile=self.profile, image_type=OrganizationImageTypeChoices.LOGO
        )
        OrganizationImageFactory(
            profile=self.profile, image_type=OrganizationImageTypeChoices.COVER
        )
        OrganizationImageFactory(
            profile=self.profile, image_type=OrganizationImageTypeChoices.FAVICON
        )
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)

    def test_choices_values(self):
        OrganizationImageFactory(
            profile=self.profile, image_type=OrganizationImageTypeChoices.LOGO
        )
        response = self.client.get(self.choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        result = response.data['results'][0]
        self.assertIn('value', result)
        self.assertIn('label', result)
        self.assertEqual(result['label'], OrganizationImageTypeChoices.LOGO)
