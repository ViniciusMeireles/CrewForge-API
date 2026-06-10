from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin


class OrganizationAPITestCase(APITestCaseMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.detail_url_name = 'accounts:organizations-detail'
        cls.list_url_name = 'accounts:organizations-list'
        cls.login_url_name = 'accounts:organizations-login'
        cls.list_url = reverse(cls.list_url_name)
        cls.choices_url = reverse(viewname='accounts:organizations-choices')

    def test_list_and_coices_organizations(self):
        """Test the list and choices views of the organization."""
        member = MemberFactory.create()
        user = member.user
        MemberFactory.create_batch(size=4, user=user)

        self.client.force_authenticate(user=user)

        for url in [self.list_url, self.choices_url]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, http_status.HTTP_200_OK)
            self.assertEqual(response.data.get('count'), 5)

    def test_create_organization(self):
        """Test the create view of the organization."""
        user = UserFactory.create()
        self.client.force_authenticate(user=user)

        organization_data = OrganizationFactory.build()
        payload = {
            'name': organization_data.name,
            'slug': organization_data.slug,
        }

        response = self.client.post(
            path=self.list_url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('name'), organization_data.name)
        self.assertEqual(response.data.get('slug'), organization_data.slug)

        owner_id = response.data.get('owner')
        owner = MemberFactory._meta.model.objects.get(id=owner_id)
        self.assertEqual(owner.user_id, user.id)

    def test_login_organization(self):
        """Test the login view of the organization."""
        member1 = MemberFactory.create()
        user = member1.user
        self.client.force_authenticate(user=user)

        url = reverse(self.login_url_name, args=[member1.organization_id])
        response = self.client.post(path=url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        self.assertEqual(
            self.client.session.get('organization_id'), member1.organization_id
        )
        self.assertIn('user', response.data)
        self.assertIn('organizations', response.data)
        self.assertIn('organization', response.data)
        self.assertIn('member', response.data)
        self.assertEqual(response.data['organization']['id'], member1.organization_id)
        self.assertEqual(response.data['member']['id'], member1.id)

        member2 = MemberFactory.create(user=user)
        url = reverse(self.login_url_name, args=[member2.organization_id])
        response = self.client.post(path=url, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(
            self.client.session.get('organization_id'), member2.organization_id
        )
        self.assertEqual(response.data['organization']['id'], member2.organization_id)
        self.assertEqual(response.data['member']['id'], member2.id)

        self.assertNotEqual(member1.organization_id, member2.organization_id)

    def test_login_organization_not_exists(self):
        """Test the login view of the organization that does not exist."""
        user = UserFactory.create()
        self.client.force_authenticate(user=user)

        url = reverse(self.login_url_name, args=[9999])
        response = self.client.post(
            path=url,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_retrieve_organization(self):
        """Test the retrieve view of the organization."""
        organization = OrganizationFactory.create()
        url = reverse(self.detail_url_name, args=[organization.id])

        response = self.client.get(
            path=url,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), organization.name)
        self.assertEqual(response.data.get('slug'), organization.slug)
        self.assertEqual(response.data.get('owner'), organization.owner_id)

    def test_update_organization(self):
        """Test the update view of the organization."""
        organization = self.new_account()

        url = reverse(self.detail_url_name, args=[organization.id])

        organization_data = OrganizationFactory.build()

        payload = {
            'name': organization_data.name,
            'slug': organization_data.slug,
        }

        response = self.client.put(
            path=url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data.get('name'), organization_data.name)
        self.assertEqual(response.data.get('slug'), organization_data.slug)
        self.assertEqual(response.data.get('owner'), organization.owner_id)

    def test_update_organization_not_role_permission(self):
        """Test the update view of the organization without role permission."""
        organization = self.new_account()

        members = [
            MemberFactory.create(organization=organization, role=role)
            for role in MemberRoleChoices.values
            if role != MemberRoleChoices.OWNER
        ]
        organization_data = OrganizationFactory.build()
        payload = {
            'name': organization_data.name,
            'slug': organization_data.slug,
        }
        for member in members:
            self.client.force_authenticate(member=member)
            url = reverse(self.detail_url_name, args=[organization.id])
            response = self.client.put(
                path=url,
                data=payload,
                format='json',
            )
            self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

        # Update with non-member user
        organization_2 = OrganizationFactory.create()
        self.client.force_authenticate(member=organization.owner)
        url = reverse(self.detail_url_name, args=[organization_2.id])
        response = self.client.put(
            path=url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

        # Update without authentication
        self.client.force_authenticate(user=None)
        url = reverse(self.detail_url_name, args=[organization.id])
        response = self.client.put(
            path=url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_delete_organization(self):
        """Test the delete view of the organization."""
        organization = self.new_account()

        url = reverse(self.detail_url_name, args=[organization.id])

        response = self.client.delete(
            path=url,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_delete_organization_not_role_permission(self):
        """Test the delete view of the organization without role permission."""
        organization = self.new_account()

        members = [
            MemberFactory.create(organization=organization, role=role)
            for role in MemberRoleChoices.values
            if role != MemberRoleChoices.OWNER
        ]
        for member in members:
            self.client.force_authenticate(member=member)
            url = reverse(self.detail_url_name, args=[organization.id])
            response = self.client.delete(
                path=url,
                format='json',
            )
            self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

        # Delete with non-member user
        organization_2 = OrganizationFactory.create()
        self.client.force_authenticate(member=organization.owner)
        url = reverse(self.detail_url_name, args=[organization_2.id])
        response = self.client.delete(
            path=url,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

        # Delete without authentication
        self.client.force_authenticate(user=None)
        url = reverse(self.detail_url_name, args=[organization.id])
        response = self.client.delete(
            path=url,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_duplicate_slug_organization(self):
        organization1 = self.new_account(login=False)
        organization_data = OrganizationFactory.build()
        payload = {
            'name': organization_data.name,
            'slug': organization1.slug,
        }

        response = self.client.post(
            path=self.list_url,
            data=payload,
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
