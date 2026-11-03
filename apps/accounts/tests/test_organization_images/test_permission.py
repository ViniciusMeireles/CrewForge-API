from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices, OrganizationImageTypeChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organization_image import OrganizationImageFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.tests.mixins import PNG_SIGNATURE, APITestCaseMixin
from apps.accounts.tests.permission_matrix import (
    ADMIN,
    ANONYMOUS,
    INACTIVE,
    MANAGER,
    MEMBER,
    OTHER_ORGANIZATION,
    OWNER,
    Action,
    PermissionMatrixMixin,
)

LIST = reverse('accounts:organization_images-list')
FORM_OPTIONS = reverse('accounts:organization_images-form-options-create')


def _detail(case):
    image = OrganizationImageFactory(profile=case.organization.get_profile())
    return reverse('accounts:organization_images-detail', args=[image.pk])


def _upload(case):
    return {
        'image.file': SimpleUploadedFile(
            name='cover.png',
            content=PNG_SIGNATURE + b'fake-png-content',
            content_type='image/png',
        ),
        'image_type': OrganizationImageTypeChoices.COVER,
    }


def _image_type(case):
    return {'image_type': 'cover'}


class OrganizationImagePermissionMatrixTestCase(
    PermissionMatrixMixin, APITestCaseMixin, APITestCase
):
    actions = {
        'list': Action('get', lambda case: LIST),
        'retrieve': Action('get', _detail),
        'create': Action('post', lambda case: LIST, _upload, 'multipart'),
        'update': Action('patch', _detail, _image_type, 'multipart'),
        'delete': Action('delete', _detail),
        'form_options': Action('get', lambda case: FORM_OPTIONS),
    }
    matrix = {
        ANONYMOUS: {
            'list': 200,
            'retrieve': 404,
            'create': 401,
            'update': 401,
            'delete': 401,
            'form_options': 200,
        },
        INACTIVE: {'create': 403, 'retrieve': 404, 'update': 404, 'delete': 404},
        OWNER: {'create': 201, 'retrieve': 200, 'update': 200, 'delete': 204},
        ADMIN: {'create': 201, 'retrieve': 200, 'update': 200, 'delete': 204},
        MANAGER: {'create': 403, 'retrieve': 200, 'update': 403, 'delete': 403},
        MEMBER: {
            'create': 403,
            'retrieve': 200,
            'update': 403,
            'delete': 403,
            'form_options': 200,
        },
        OTHER_ORGANIZATION: {'retrieve': 404, 'update': 404, 'delete': 404},
    }

    def setUp(self):
        self.organization = OrganizationFactory()


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
        self._create_image()
        self.client.logout()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_list_returns_only_session_organization_images(self):
        own = self._create_image()
        OrganizationImageFactory(profile=OrganizationFactory().get_profile())
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in response.data['results']], [own.id])

    def test_not_authenticated_form_options_ignores_search(self):
        self.client.logout()
        url = reverse(viewname='accounts:organization_images-form-options-create')
        response = self.client.get(url, {'image_type': r'(\w|\w)*\d'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            len(response.data['image_type']), len(OrganizationImageTypeChoices)
        )

    def _create_payload(self, image_type=OrganizationImageTypeChoices.COVER):
        return {
            'image.file': SimpleUploadedFile(
                name='cover.png',
                content=PNG_SIGNATURE + b'fake-png-content',
                content_type='image/png',
            ),
            'image_type': image_type,
        }

    def _create_as(self, role):
        if role != MemberRoleChoices.OWNER:
            member = MemberFactory(organization=self.organization, role=role)
            self.client.force_authenticate(member=member)
        return self.client.post(
            self.list_url, data=self._create_payload(), format='multipart'
        )

    def test_manager_cannot_create(self):
        response = self._create_as(MemberRoleChoices.MANAGER)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.profile.images.exists())

    def test_member_cannot_create(self):
        response = self._create_as(MemberRoleChoices.MEMBER)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.profile.images.exists())
