from django.urls import reverse

from apps.accounts.tests.mixins import APITestCaseMixin
from apps.audit.models.audit_event import AuditEvent

LIST_URL = 'audit:audit_events-list'
DETAIL_URL = 'audit:audit_events-detail'


class AuditAPITestCaseMixin(APITestCaseMixin):
    def setUp(self):
        self.organization = self.new_account()
        self.owner = self.organization.owner
        self.clear_events()

    @staticmethod
    def clear_events():
        AuditEvent.objects.all().delete()

    def list_events(self, **params):
        return self.client.get(reverse(LIST_URL), params)

    def retrieve_event(self, event):
        return self.client.get(reverse(DETAIL_URL, args=[event.pk]))

    def events(self, action=None):
        queryset = AuditEvent.objects.all()
        return queryset.filter(action=action) if action else queryset
