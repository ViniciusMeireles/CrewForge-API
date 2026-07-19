from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import OrganizationImageTypeChoices
from apps.accounts.factories.organization_image import OrganizationImageFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationImageFilterTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.profile = self.organization.get_profile()
        self.list_url = reverse(viewname='accounts:organization_images-list')

        self.logo_img = OrganizationImageFactory(
            profile=self.profile,
            image_type=OrganizationImageTypeChoices.LOGO,
        )
        self.cover_img = OrganizationImageFactory(
            profile=self.profile,
            image_type=OrganizationImageTypeChoices.COVER,
        )
        self.inactive_img = OrganizationImageFactory(
            profile=self.profile,
            image_type=OrganizationImageTypeChoices.FAVICON,
            is_active=False,
        )

    def test_filter_by_organization(self):
        other_org = OrganizationFactory()
        other_profile = other_org.get_profile()
        OrganizationImageFactory(profile=other_profile)

        response = self.client.get(
            self.list_url, {'organization': self.organization.id}
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for result in response.data['results']:
            img = OrganizationImageFactory._meta.model.objects.get(id=result['id'])
            self.assertEqual(img.profile.organization_id, self.organization.id)

    def test_filter_image_type_exact(self):
        response = self.client.get(
            self.list_url, {'image_type': OrganizationImageTypeChoices.LOGO}
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(
            response.data['results'][0]['image_type'],
            OrganizationImageTypeChoices.LOGO,
        )

    def test_filter_image_type_cover(self):
        response = self.client.get(
            self.list_url, {'image_type': OrganizationImageTypeChoices.COVER}
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(
            response.data['results'][0]['image_type'],
            OrganizationImageTypeChoices.COVER,
        )

    def test_filter_combined(self):
        response = self.client.get(
            self.list_url,
            {
                'image_type': OrganizationImageTypeChoices.LOGO,
                'organization': self.organization.id,
            },
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_order_by_image_type_ascending(self):
        response = self.client.get(self.list_url, {'order_by': 'image_type'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        image_types = [r['image_type'] for r in response.data['results']]
        self.assertEqual(image_types, sorted(image_types))

    def test_filter_order_by_image_type_descending(self):
        response = self.client.get(self.list_url, {'order_by': '-image_type'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        image_types = [r['image_type'] for r in response.data['results']]
        self.assertEqual(image_types, sorted(image_types, reverse=True))

    def test_filter_order_by_invalid_field(self):
        response = self.client.get(self.list_url, {'order_by': 'bogus'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_filter_order_by_with_image_type_filter(self):
        response = self.client.get(
            self.list_url,
            {'order_by': 'image_type', 'image_type': OrganizationImageTypeChoices.LOGO},
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        for r in response.data['results']:
            self.assertEqual(r['image_type'], OrganizationImageTypeChoices.LOGO)
