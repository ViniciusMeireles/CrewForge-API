from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.accounts.factories.users import UserFactory
from apps.accounts.tests.mixins import APITestCaseMixin
from apps.audit.choices import AuditActionChoices
from apps.audit.factories.audit_event import AuditEventFactory
from apps.audit.models.audit_event import AuditEvent

URL = 'accounts:users-me-activity'


class UserActivityTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        AuditEvent.objects.all().delete()

    def activity(self, **params):
        return self.client.get(reverse(URL), params)

    def test_lists_own_account_events(self):
        own = AuditEventFactory(account=True, actor_user=self.user)
        AuditEventFactory(account=True)
        response = self.activity()
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in response.data['results']], [own.pk])

    def test_includes_failed_sign_ins_targeting_the_user(self):
        failed = AuditEventFactory(
            account=True,
            actor_user=None,
            actor_label='',
            subject_user=self.user,
            action=AuditActionChoices.AUTH_LOGIN_FAILED,
        )
        ids = [item['id'] for item in self.activity().data['results']]
        self.assertEqual(ids, [failed.pk])

    def test_excludes_organization_events(self):
        AuditEventFactory(actor_member__user=self.user)
        self.assertEqual(self.activity().data['count'], 0)

    def test_is_paginated(self):
        for _ in range(12):
            AuditEventFactory(account=True, actor_user=self.user)
        response = self.activity()
        self.assertEqual(response.data['count'], 12)
        self.assertEqual(len(response.data['results']), 10)

    def test_works_without_organization_context(self):
        self.assertEqual(self.activity().status_code, http_status.HTTP_200_OK)

    def test_not_authenticated(self):
        self.client.logout()
        self.assertEqual(self.activity().status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_write_methods_are_not_allowed(self):
        response = self.client.post(reverse(URL), {}, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_405_METHOD_NOT_ALLOWED)
