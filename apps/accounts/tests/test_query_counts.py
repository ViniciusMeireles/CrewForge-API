from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.models.organization import Organization, OrganizationProfile
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.audit.choices import AuditActionChoices
from apps.audit.services import record_audit_event


def _count(client, url):
    with CaptureQueriesContext(connection) as queries:
        response = client.get(url, {'page_size': 50})
    assert response.status_code == http_status.HTTP_200_OK, response.data
    return len(queries.captured_queries), queries


class ListQueryCountTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()

    def _grow(self, make, count):
        for _ in range(count):
            make()

    def test_member_list_queries_do_not_grow(self):
        url = reverse('accounts:members-list')
        self._grow(lambda: MemberFactory(organization=self.organization), 4)
        small, _ = _count(self.client, url)
        self._grow(lambda: MemberFactory(organization=self.organization), 20)
        large, _ = _count(self.client, url)
        self.assertEqual(small, large)

    def test_organization_list_queries_do_not_grow(self):
        url = reverse('accounts:organizations-list')
        user = self.organization.owner.user

        def join():
            MemberFactory(organization=OrganizationFactory(), user=user)

        self._grow(join, 4)
        small, _ = _count(self.client, url)
        self._grow(join, 20)
        large, queries = _count(self.client, url)
        self.assertEqual(small, large)
        self.assertFalse(
            [q for q in queries.captured_queries if q['sql'].startswith('INSERT')]
        )

    def test_audit_list_queries_do_not_grow(self):
        url = reverse('audit:audit_events-list')

        def event():
            record_audit_event(
                AuditActionChoices.MEMBER_UPDATED,
                organization_id=self.organization.pk,
                actor_member=MemberFactory(organization=self.organization),
                target=self.organization,
            )

        self._grow(event, 4)
        small, _ = _count(self.client, url)
        self._grow(event, 20)
        large, _ = _count(self.client, url)
        self.assertEqual(small, large)


class OrganizationProfileTestCase(APITestCaseMixin, APITestCase):
    def test_created_organization_has_a_profile(self):
        self.new_account(login=True, organization_login=False)
        response = self.client.post(
            reverse('accounts:organizations-list'),
            data={'name': 'Fresh', 'slug': 'fresh'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        organization = Organization.objects.get(slug='fresh')
        self.assertTrue(
            OrganizationProfile.objects.filter(organization=organization).exists()
        )

    def test_factory_organization_has_a_profile(self):
        organization = OrganizationFactory()
        self.assertTrue(
            OrganizationProfile.objects.filter(organization=organization).exists()
        )

    def test_get_profile_never_creates(self):
        organization = OrganizationFactory()
        OrganizationProfile.objects.filter(organization=organization).delete()
        organization = Organization.objects.get(pk=organization.pk)
        self.assertIsNone(organization.get_profile())
        self.assertFalse(
            OrganizationProfile.objects.filter(organization=organization).exists()
        )
