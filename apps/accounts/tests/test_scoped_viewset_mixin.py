from django.contrib.sessions.backends.db import SessionStore
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, APITestCase

from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.views.members import MemberViewSet


class OrganizationScopedViewSetMixinTestCase(APITestCase):
    def _view(self, user, organization_id=None):
        django_request = APIRequestFactory().get('/')
        django_request.user = user
        django_request.session = SessionStore()
        if organization_id:
            django_request.session['organization_id'] = organization_id
        request = Request(django_request)
        request.user = user
        view = MemberViewSet()
        view.request = request
        view.action = 'list'
        view.kwargs = {}
        view.format_kwarg = None
        return view

    def test_queryset_is_empty_without_organization_context(self):
        organization = OrganizationFactory()
        view = self._view(organization.owner.user)
        queryset = view.get_queryset()
        with self.assertNumQueries(0):
            self.assertEqual(list(queryset), [])

    def test_queryset_is_scoped_to_session_organization(self):
        organization = OrganizationFactory()
        OrganizationFactory()
        view = self._view(organization.owner.user, organization.id)
        self.assertEqual(list(view.get_queryset()), [organization.owner])

    def test_queryset_is_empty_when_session_organization_is_not_the_users(self):
        organization = OrganizationFactory()
        stranger = OrganizationFactory().owner.user
        view = self._view(stranger, organization.id)
        self.assertFalse(view.get_queryset().exists())

    def test_queryset_is_empty_for_inactive_member(self):
        organization = OrganizationFactory()
        member = MemberFactory(organization=organization, is_active=False)
        view = self._view(member.user, organization.id)
        self.assertFalse(view.get_queryset().exists())
