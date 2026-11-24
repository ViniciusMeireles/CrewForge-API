from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.choices import MemberRoleChoices, OrganizationImageTypeChoices
from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.factories.invitations import InvitationFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.models.files import StoredFile
from apps.accounts.models.member import Member
from apps.accounts.models.user import User
from apps.accounts.tests.mixins import PNG_SIGNATURE, APITestCaseMixin
from apps.billing.entitlements import BYTES_PER_MB
from apps.billing.tests.helpers import set_plan
from apps.teams.factories.teams import TeamFactory
from apps.teams.models.team import Team


class LimitTestMixin(APITestCaseMixin):
    def assert_limit(self, response, limit: str, current: int, maximum: int):
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        error = response.data['error']
        self.assertEqual(error['code'], 'PLAN_LIMIT_REACHED')
        self.assertEqual(
            error['details'], {'limit': limit, 'current': current, 'max': maximum}
        )


class InvitationLimitTestCase(LimitTestMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.url = reverse('accounts:invitations-list')

    def invite(self):
        return self.client.post(
            self.url,
            data={'email': 'new@example.com', 'role': MemberRoleChoices.MEMBER},
            format='json',
        )

    def test_invitation_at_member_limit(self):
        MemberFactory.create_batch(4, organization=self.organization)
        set_plan(self.organization, max_members=5)
        response = self.invite()
        self.assert_limit(response, 'max_members', 5, 5)
        self.assertIn('5 members', response.data['error']['message'])

    def test_pending_invitations_count(self):
        MemberFactory.create_batch(2, organization=self.organization)
        InvitationFactory.create_batch(2, organization=self.organization)
        set_plan(self.organization, max_members=5)
        self.assert_limit(self.invite(), 'max_members', 5, 5)

    def test_expired_and_removed_do_not_count(self):
        InvitationFactory(organization=self.organization, is_expired=True)
        MemberFactory(organization=self.organization, is_active=False)
        set_plan(self.organization, max_members=2)
        self.assertEqual(self.invite().status_code, http_status.HTTP_201_CREATED)

    def test_unlimited(self):
        MemberFactory.create_batch(5, organization=self.organization)
        set_plan(self.organization, max_members=None)
        self.assertEqual(self.invite().status_code, http_status.HTTP_201_CREATED)

    def test_validation_error_comes_first(self):
        set_plan(self.organization, max_members=1)
        response = self.client.post(self.url, data={'email': 'bad'}, format='json')
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')

    def test_role_permission_comes_first(self):
        manager = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MANAGER
        )
        set_plan(self.organization, max_members=1)
        self.client.force_authenticate(member=manager)
        self.assertEqual(self.invite().data['error']['code'], 'PERMISSION_DENIED')

    def test_other_organization_does_not_count(self):
        other = OrganizationFactory()
        MemberFactory.create_batch(5, organization=other)
        set_plan(self.organization, max_members=2)
        self.assertEqual(self.invite().status_code, http_status.HTTP_201_CREATED)


class AcceptanceLimitTestCase(LimitTestMixin, APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.user = UserFactory()
        self.invitation = InvitationFactory(
            organization=self.organization, email=self.user.email
        )
        set_plan(self.organization, max_members=1)

    def accept(self):
        self.client.force_authenticate(user=self.user)
        return self.client.post(
            reverse(
                'accounts:invitations-accept',
                kwargs={'invitation_pk': self.invitation.pk},
            ),
            format='json',
        )

    def test_acceptance_at_the_limit(self):
        self.assert_limit(self.accept(), 'max_members', 1, 1)
        self.assertFalse(
            Member.objects.filter(
                user=self.user, organization=self.organization
            ).exists()
        )
        self.invitation.refresh_from_db()
        self.assertIsNone(self.invitation.accepted_at)

    def test_readmission_at_the_limit(self):
        MemberFactory(user=self.user, organization=self.organization, is_active=False)
        self.assert_limit(self.accept(), 'max_members', 1, 1)
        self.assertFalse(
            Member.objects.get(user=self.user, organization=self.organization).is_active
        )

    def test_acceptance_within_the_limit(self):
        set_plan(self.organization, max_members=2)
        self.assertEqual(self.accept().status_code, http_status.HTTP_200_OK)


class CreateWithInviteLimitTestCase(LimitTestMixin, APITestCase):
    def test_signup_at_the_limit_creates_nothing(self):
        organization = OrganizationFactory()
        set_plan(organization, max_members=1)
        data = UserFactory.build()
        invitation = InvitationFactory(organization=organization, email=data.email)
        response = self.client.post(
            reverse('accounts:members-create-with-invite', args=[invitation.key]),
            data={
                'user': {
                    'username': data.username,
                    'email': data.email,
                    'first_name': data.first_name,
                    'last_name': data.last_name,
                    'password': data.password,
                },
            },
            format='json',
        )
        self.assert_limit(response, 'max_members', 1, 1)
        self.assertFalse(User.objects.filter(email=data.email).exists())


class TeamLimitTestCase(LimitTestMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.url = reverse('teams:teams-list')

    def create_team(self):
        return self.client.post(self.url, data={'name': 'Platform'}, format='json')

    def test_teams_above_limit_kept_and_create_refused(self):
        TeamFactory.create_batch(8, organization=self.organization)
        set_plan(self.organization, max_teams=5)
        self.assert_limit(self.create_team(), 'max_teams', 8, 5)
        self.assertEqual(
            Team.objects.filter(organization=self.organization, is_active=True).count(),
            8,
        )

    def test_inactive_teams_do_not_count(self):
        TeamFactory(organization=self.organization, is_active=False)
        set_plan(self.organization, max_teams=1)
        self.assertEqual(self.create_team().status_code, http_status.HTTP_201_CREATED)

    def test_member_role_refused_before_limit(self):
        member = MemberFactory(
            organization=self.organization, role=MemberRoleChoices.MEMBER
        )
        set_plan(self.organization, max_teams=0)
        self.client.force_authenticate(member=member)
        self.assertEqual(self.create_team().data['error']['code'], 'PERMISSION_DENIED')


class StorageLimitTestCase(LimitTestMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.used = BYTES_PER_MB - 5
        StoredFileFactory(organization=self.organization)
        self.organization.stored_files.update(size=self.used)
        set_plan(self.organization, storage_mb=1)

    def upload(self, content=b'Hello, World!'):
        return self.client.post(
            reverse('accounts:stored_files-list'),
            data={
                'file': SimpleUploadedFile('a.txt', content, content_type='text/plain'),
                'viewing_permission': 'members_organization',
                'updating_permission': 'members_organization',
            },
            format='multipart',
        )

    def test_upload_over_storage(self):
        self.assert_limit(self.upload(), 'storage_bytes', self.used, BYTES_PER_MB)

    def test_upload_within_storage(self):
        self.assertEqual(self.upload(b'1234').status_code, http_status.HTTP_201_CREATED)

    def test_organization_image_over_storage(self):
        response = self.client.post(
            reverse('accounts:organization_images-list'),
            data={
                'image.file': SimpleUploadedFile(
                    'logo.png',
                    PNG_SIGNATURE + b'fake-png-content',
                    content_type='image/png',
                ),
                'image_type': OrganizationImageTypeChoices.LOGO,
            },
            format='multipart',
        )
        self.assert_limit(response, 'storage_bytes', self.used, BYTES_PER_MB)

    def test_replacing_with_a_smaller_file_passes(self):
        stored = self.organization.stored_files.get()
        stored.viewing_permission = 'members_organization'
        stored.updating_permission = 'members_organization'
        stored.save()
        self.organization.stored_files.update(size=self.used)
        response = self.client.patch(
            reverse('accounts:stored_files-detail', args=[stored.uuid]),
            data={
                'file': SimpleUploadedFile('b.txt', b'tiny', content_type='text/plain')
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_files_without_organization_do_not_count(self):
        StoredFileFactory(organization=None, owner=self.organization.owner.user)
        StoredFile.objects.filter(organization__isnull=True).update(size=BYTES_PER_MB)
        self.assertEqual(self.upload(b'1234').status_code, http_status.HTTP_201_CREATED)

    def test_deleted_files_do_not_count(self):
        self.organization.stored_files.update(is_active=False)
        response = self.upload(b'x' * 100)
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)


class AdmitCallersTestCase(SimpleTestCase):
    def test_every_admit_caller_checks_the_member_limit(self):
        root = Path(settings.BASE_DIR) / 'apps'
        callers = sorted(
            str(path.relative_to(root))
            for path in root.rglob('*.py')
            if 'tests' not in path.parts and 'Member.objects.admit(' in path.read_text()
        )
        self.assertEqual(callers, ['accounts/services/invitations.py'])
        source = (root / 'accounts/services/invitations.py').read_text()
        self.assertLess(
            source.index('ensure_within_limit('), source.index('Member.objects.admit(')
        )
