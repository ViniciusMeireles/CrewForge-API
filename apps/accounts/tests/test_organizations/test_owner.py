import uuid

from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.models.member import Member
from apps.accounts.models.organization import Organization
from apps.accounts.tests.mixins import APITestCaseMixin


class SingleOwnerConstraintTestCase(TestCase):
    def test_second_active_owner_is_refused(self):
        organization = OrganizationFactory()
        with self.assertRaises(IntegrityError):
            Member.objects.create(
                organization=organization,
                user=MemberFactory().user,
                role=MemberRoleChoices.OWNER,
            )

    def test_inactive_owner_does_not_count(self):
        organization = OrganizationFactory()
        organization.owner.role = MemberRoleChoices.ADMIN
        organization.owner.save(update_fields=['role'])
        MemberFactory(
            organization=organization, role=MemberRoleChoices.OWNER, is_active=False
        )
        MemberFactory(organization=organization, role=MemberRoleChoices.OWNER)

    def test_duplicate_membership_is_refused(self):
        member = MemberFactory()
        with self.assertRaises(IntegrityError):
            MemberFactory(user=member.user, organization=member.organization)


class OwnerSourceTestCase(TestCase):
    def test_owner_is_the_active_owner_member(self):
        organization = OrganizationFactory()
        owner = Member.objects.get(
            organization=organization, role=MemberRoleChoices.OWNER
        )
        self.assertEqual(organization.owner, owner)

    def test_owner_is_none_without_active_owner(self):
        organization = OrganizationFactory()
        Member.objects.filter(organization=organization).update(is_active=False)
        self.assertIsNone(Organization.objects.get(pk=organization.pk).owner)

    def test_with_owner_loads_owner_in_bulk(self):
        organizations = [OrganizationFactory() for _ in range(3)]
        queryset = Organization.objects.filter(
            pk__in=[o.pk for o in organizations]
        ).with_owner()
        with self.assertNumQueries(2):
            owners = {o.pk: o.owner.user.email for o in queryset}
        self.assertEqual(len(owners), 3)


class OwnerApiTestCase(APITestCaseMixin, APITestCase):
    def test_detail_exposes_owner_member_id(self):
        organization = self.new_account()
        url = reverse('accounts:organizations-detail', args=[organization.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['owner'], organization.owner.pk)

    def test_signup_creates_a_single_owner(self):
        response = self.client.post(
            reverse('accounts:signup-list'),
            data={
                'user': {
                    'username': 'solo',
                    'email': 'solo@example.com',
                    'first_name': 'Solo',
                    'last_name': 'Owner',
                    'password': 'passWord*123',
                },
                'organization': {'name': 'Solo Org', 'slug': 'solo-org'},
            },
            format='json',
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        organization = Organization.objects.get(slug='solo-org')
        self.assertEqual(
            Member.objects.filter(
                organization=organization, role=MemberRoleChoices.OWNER
            ).count(),
            1,
        )
        self.assertEqual(organization.owner.user.username, 'solo')


class SingleOwnerMigrationTestCase(TransactionTestCase):
    before = [('accounts', '0014_invitation_uniqueness')]
    after = [('accounts', '0016_single_owner')]

    def _migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_owner_fk_wins_over_extra_owner_roles(self):
        apps = self._migrate(self.before)
        Organization = apps.get_model('accounts', 'Organization')
        OldMember = apps.get_model('accounts', 'Member')
        User = apps.get_model('accounts', 'User')
        slug = f'acme-{uuid.uuid4().hex[:8]}'
        organization = Organization.objects.create(name=slug, slug=slug)
        first, second = (
            OldMember.objects.create(
                organization=organization,
                user=User.objects.create(username=f'{slug}-{n}', email=f'{n}@x.com'),
                role='owner',
            )
            for n in (1, 2)
        )
        organization.owner = second
        organization.save(update_fields=['owner'])
        apps = self._migrate(self.after)
        NewMember = apps.get_model('accounts', 'Member')
        self.assertEqual(NewMember.objects.get(pk=second.pk).role, 'owner')
        self.assertEqual(NewMember.objects.get(pk=first.pk).role, 'admin')
