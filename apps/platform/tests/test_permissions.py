from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.platform.tests.mixins import PlatformTestMixin


class PlatformPermissionTestCase(PlatformTestMixin, APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.user = UserFactory()
        self.urls = [
            reverse('platform:overview'),
            reverse('platform:organizations-list'),
            reverse('platform:organizations-detail', args=[self.organization.id]),
            reverse('platform:organizations-members', args=[self.organization.id]),
            reverse('platform:organizations-teams', args=[self.organization.id]),
            reverse('platform:organizations-invitations', args=[self.organization.id]),
            reverse('platform:users-list'),
            reverse('platform:users-detail', args=[self.user.id]),
            reverse('platform:audit_events-list'),
        ]

    def test_unauthenticated_is_refused(self):
        for url in self.urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(
                    response.status_code, http_status.HTTP_401_UNAUTHORIZED
                )

    def test_role_none_is_forbidden_on_every_route(self):
        self.client.force_authenticate(user=UserFactory())
        for url in self.urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_role_none_superuser_is_forbidden(self):
        self.client.force_authenticate(user=UserFactory(is_superuser=True))
        response = self.client.get(reverse('platform:overview'))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_support_reads_without_organization_context(self):
        self.authenticate_staff('support')
        for url in self.urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_admin_reads_every_route(self):
        self.authenticate_staff('admin')
        for url in self.urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_routes_are_read_only(self):
        self.authenticate_staff('admin')
        url = reverse('platform:organizations-detail', args=[self.organization.id])
        response = self.client.patch(url, data={'name': 'x'}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_405_METHOD_NOT_ALLOWED)
