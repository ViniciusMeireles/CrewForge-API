from django.test import RequestFactory, TestCase

from apps.accounts.choices import MemberRoleChoices, StoredFileAccess
from apps.accounts.factories.files import StoredFileFactory
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.factories.users import UserFactory
from apps.accounts.forms.files import StoredFileModelForm


class StoredFileModelFormTestCase(TestCase):
    def setUp(self):
        self.stored_file = StoredFileFactory()
        self.data = {
            'name': 'renamed',
            'viewing_permission': StoredFileAccess.OWNER,
            'updating_permission': StoredFileAccess.OWNER,
            'owner': self.stored_file.owner_id,
            'organization': self.stored_file.organization_id,
        }

    def form(self, upload_too_large, data=None, session=None, user=None):
        request = RequestFactory().post('/admin/')
        request.user = user or UserFactory(is_superuser=True, is_staff=True)
        request.session = session or {}
        request.upload_too_large = upload_too_large
        return StoredFileModelForm(
            data=data or self.data, instance=self.stored_file, request=request
        )

    def test_edit_without_new_file_keeps_the_file(self):
        form = self.form(upload_too_large=False)
        self.assertTrue(form.is_valid(), form.errors)

    def test_edit_with_dropped_oversized_file_reports_error(self):
        form = self.form(upload_too_large=True)
        self.assertFalse(form.is_valid())
        self.assertIn('too large', str(form.errors['file']))

    def test_admin_can_move_the_file_to_another_organization(self):
        other_organization = OrganizationFactory()
        form = self.form(
            upload_too_large=False,
            data={**self.data, 'organization': other_organization.id},
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['organization'], other_organization)

    def test_admin_sets_any_access_level_regardless_of_session_role(self):
        user = UserFactory(is_superuser=True, is_staff=True)
        member = MemberFactory(user=user, role=MemberRoleChoices.MEMBER)
        form = self.form(
            upload_too_large=False,
            user=user,
            session={'organization_id': member.organization_id},
            data={
                **self.data,
                'viewing_permission': StoredFileAccess.ADMINS_ORGANIZATION,
                'updating_permission': StoredFileAccess.OWNERS_ORGANIZATION,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_admin_blank_organization_is_not_taken_from_the_session(self):
        user = UserFactory(is_superuser=True, is_staff=True)
        member = MemberFactory(user=user, role=MemberRoleChoices.OWNER)
        form = self.form(
            upload_too_large=False,
            user=user,
            session={'organization_id': member.organization_id},
            data={**self.data, 'organization': ''},
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['organization'])
