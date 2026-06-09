from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationProfileIntegrationTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.profile = self.organization.get_profile()
        self.list_url = reverse(viewname='accounts:organization_profiles-list')
        self.detail_url = reverse(
            viewname='accounts:organization_profiles-detail',
            args=[self.profile.id],
        )

    def test_full_crud_flow(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        profile_id = response.data['results'][0]['id']

        url = reverse(
            viewname='accounts:organization_profiles-detail',
            args=[profile_id],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['id'], profile_id)

        response = self.client.patch(
            url,
            data={'website': 'https://updated.com'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['website'], 'https://updated.com')

        response = self.client.delete(url)
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_permission_read_all_roles(self):
        roles = [
            MemberRoleChoices.OWNER,
            MemberRoleChoices.ADMIN,
            MemberRoleChoices.MANAGER,
            MemberRoleChoices.MEMBER,
        ]
        for role in roles:
            if role == MemberRoleChoices.OWNER:
                self.client.force_authenticate(member=self.organization.owner)
            else:
                member = MemberFactory(organization=self.organization, role=role)
                self.client.force_authenticate(member=member)
            response = self.client.get(self.detail_url)
            self.assertEqual(
                response.status_code,
                http_status.HTTP_200_OK,
                f'{role} should be able to retrieve',
            )

    def test_permission_write_admin_only(self):
        admin = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.ADMIN
        )
        self.client.force_authenticate(member=admin)
        response = self.client.patch(
            self.detail_url,
            data={'website': 'https://admin-write.com'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        self.client.force_authenticate(member=manager)
        response = self.client.patch(
            self.detail_url,
            data={'website': 'https://manager-write.com'},
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_choices_reflects_after_update(self):
        choices_url = reverse(viewname='accounts:organization_profiles-choices')
        response = self.client.get(choices_url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
        self.assertEqual(
            response.data['results'][0]['label'],
            self.organization.name,
        )

    def test_cross_org_isolation(self):
        from apps.accounts.factories.organizations import OrganizationFactory

        other_org = OrganizationFactory()
        other_member = other_org.owner
        self.client.force_authenticate(member=other_member)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
