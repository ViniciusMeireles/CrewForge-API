from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.accounts.admin import CustomUserAdmin
from apps.accounts.factories.users import UserFactory
from apps.audit.choices import AuditActionChoices, AuditActorTypeChoices
from apps.audit.models.audit_event import AuditEvent

User = get_user_model()


class PlatformRoleAdminTestCase(TestCase):
    def setUp(self):
        self.admin = CustomUserAdmin(User, AdminSite())
        self.request = RequestFactory().post('/admin/')
        self.request.user = UserFactory(is_superuser=True, is_staff=True)
        self.request.session = {}

    def save(self, user, **changes):
        form_class = self.admin.get_form(self.request, user)
        data = {
            field: getattr(user, field)
            for field in form_class.base_fields
            if field not in ('password', 'groups', 'user_permissions', 'organizations')
            and not field.endswith('_at')
            and field not in ('last_login', 'date_joined', 'blocked_by')
        }
        data.update(changes)
        form = form_class(instance=user, data=data)
        form.full_clean()
        self.admin.save_model(self.request, user, form, change=True)

    def test_role_change_is_audited_with_the_staff_actor(self):
        user = UserFactory()
        self.save(user, platform_role='support')
        user.refresh_from_db()
        self.assertEqual(user.platform_role, 'support')
        event = AuditEvent.objects.get(
            action=AuditActionChoices.USER_PLATFORM_ROLE_CHANGED
        )
        self.assertEqual(event.actor_user_id, self.request.user.id)
        self.assertEqual(event.actor_type, AuditActorTypeChoices.PLATFORM)
        self.assertEqual(event.subject_user_id, user.id)

    def test_other_changes_are_not_audited_as_role_changes(self):
        user = UserFactory()
        self.save(user, first_name='Renamed')
        self.assertFalse(
            AuditEvent.objects.filter(
                action=AuditActionChoices.USER_PLATFORM_ROLE_CHANGED
            ).exists()
        )
