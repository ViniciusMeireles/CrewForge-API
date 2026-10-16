from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APITestCase

from apps.audit.factories.audit_event import AuditEventFactory
from apps.audit.tests.mixins import DETAIL_URL, LIST_URL, AuditAPITestCaseMixin


class AuditEventCRUDTestCase(AuditAPITestCaseMixin, APITestCase):
    def create_event(self, **kwargs):
        return AuditEventFactory(
            organization=self.organization, actor_member=self.owner, **kwargs
        )

    def test_list_audit_events(self):
        first, second = self.create_event(), self.create_event()
        response = self.list_events()
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(
            [item['id'] for item in response.data['results']], [second.pk, first.pk]
        )

    def test_list_is_paginated(self):
        for _ in range(12):
            self.create_event()
        response = self.list_events()
        self.assertEqual(response.data['count'], 12)
        self.assertEqual(len(response.data['results']), 10)
        self.assertIsNotNone(response.data['next'])

    def test_list_only_session_organization(self):
        self.create_event()
        AuditEventFactory()
        AuditEventFactory(account=True)
        self.assertEqual(self.list_events().data['count'], 1)

    def test_retrieve_audit_event(self):
        event = self.create_event()
        response = self.retrieve_event(event)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['id'], event.pk)

    def test_retrieve_nonexistent(self):
        response = self.client.get(reverse(DETAIL_URL, args=[999999]))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_write_methods_are_not_allowed(self):
        event = self.create_event()
        detail = reverse(DETAIL_URL, args=[event.pk])
        for method, url in (
            (self.client.post, reverse(LIST_URL)),
            (self.client.put, detail),
            (self.client.patch, detail),
            (self.client.delete, detail),
        ):
            with self.subTest(method=method.__name__):
                response = method(url, {}, format='json')
                self.assertEqual(
                    response.status_code, http_status.HTTP_405_METHOD_NOT_ALLOWED
                )
        self.assertTrue(type(event).objects.filter(pk=event.pk).exists())
