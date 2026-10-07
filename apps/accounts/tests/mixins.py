from django.urls import reverse

from apps.accounts.factories.organizations import OrganizationFactory
from apps.accounts.models.organization import Organization
from apps.accounts.tests.client import CustomAPIClient

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


class APITestCaseMixin:
    client_class = CustomAPIClient
    client: CustomAPIClient = None

    def new_account(
        self, login: bool = True, organization_login: bool = True
    ) -> Organization:
        organization = OrganizationFactory.create()
        if login:
            if organization_login:
                self.client.force_authenticate(member=organization.owner)
            else:
                self.client.force_authenticate(user=organization.owner.user)
        return organization


class FilterOptionsTestMixin:
    """
    Helpers for ``filter-options/`` tests. ``expected_status`` maps each scenario
    to ``{resource: status}``; ``filter_options_namespace`` is the URL namespace.
    """

    filter_options_namespace: str | None = None
    expected_status: dict[str, dict[str, int]] = {}

    def filter_options_urls(self, resource: str) -> tuple[str, str]:
        name = f'{self.filter_options_namespace}:{resource}'
        return reverse(f'{name}-list'), reverse(f'{name}-filter-options')

    def filter_options_url(self, resource: str) -> str:
        return self.filter_options_urls(resource)[1]

    @staticmethod
    def option_values(response, field_name: str) -> set:
        data = response.data[field_name]
        if isinstance(data, dict):
            data = data['results']
        return {option['value'] for option in data}

    def assert_expected_status(self, scenario: str) -> None:
        """Pin the status of each resource and check it matches its list."""
        for resource, expected in self.expected_status[scenario].items():
            list_url, options_url = self.filter_options_urls(resource)
            with self.subTest(scenario=scenario, resource=resource):
                status = self.client.get(options_url).status_code
                self.assertEqual(status, expected)
                self.assertEqual(self.client.get(list_url).status_code, status)
