from django.test import RequestFactory, TestCase

from apps.accounts.choices import StoredFileAccess
from apps.accounts.factories.files import StoredFileFactory
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

    def form(self, upload_too_large):
        request = RequestFactory().post('/admin/')
        request.user = UserFactory(is_superuser=True, is_staff=True)
        request.session = {}
        request.upload_too_large = upload_too_large
        return StoredFileModelForm(
            data=self.data, instance=self.stored_file, request=request
        )

    def test_edit_without_new_file_keeps_the_file(self):
        form = self.form(upload_too_large=False)
        self.assertTrue(form.is_valid(), form.errors)

    def test_edit_with_dropped_oversized_file_reports_error(self):
        form = self.form(upload_too_large=True)
        self.assertFalse(form.is_valid())
        self.assertIn('too large', str(form.errors['file']))
