from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin


# ============================================================
# test_model.py — Model-level behavior tests
# ============================================================

# Add to apps/{app}/tests/test_{resource}/test_model.py

class {Resource}ModelTestCase(TestCase):
    def test_str(self):
        """Test __str__ returns expected format."""
        resource = {Resource}Factory()
        self.assertEqual(str(resource), '{expected_str}')

    def test_filter_actives(self):
        """Test filter_actives excludes inactive."""
        {Resource}Factory(is_active=True)
        {Resource}Factory(is_active=False)
        active = {Resource}.objects.filter_actives()
        self.assertEqual(active.count(), 1)

    def test_filter_inactives(self):
        """Test filter_inactives excludes active."""
        {Resource}Factory(is_active=True)
        {Resource}Factory(is_active=False)
        inactive = {Resource}objects.filter_inactives()
        self.assertEqual(inactive.count(), 1)

    def test_get_or_none_found(self):
        """Test get_or_none returns object when found."""
        resource = {Resource}Factory()
        result = {Resource}.objects.get_or_none(id=resource.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, resource.id)

    def test_get_or_none_not_found(self):
        """Test get_or_none returns None when not found."""
        result = {Resource}.objects.get_or_none(id=99999)
        self.assertIsNone(result)


# ============================================================
# test_choices.py — Choice enum tests
# ============================================================

class {Resource}ChoicesTestCase(TestCase):
    def test_choices_count(self):
        """Test correct number of choices."""
        self.assertEqual(len({Resource}Choices.choices), {count})

    def test_choices_values(self):
        """Test all expected values exist."""
        expected = [{values}]
        actual = [c[0] for c in {Resource}Choices.choices]
        for value in expected:
            self.assertIn(value, actual)


# ============================================================
# test_serializer.py — Serializer field contract tests
# ============================================================

class {Resource}SerializerTestCase(APITestCaseMixin, APITestCase):
    def test_list_fields(self):
        """Test list serializer returns expected fields."""
        resource = {Resource}Factory()
        serializer = {Resource}Serializer(resource)
        expected_fields = {fields}
        self.assertEqual(set(serializer.data.keys()), set(expected_fields))

    def test_create_validation_error(self):
        """Test create with missing required field."""
        payload = {}  # missing required fields
        serializer = {Resource}Serializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn('{field}', serializer.errors)


# ============================================================
# test_crud.py — CRUD operation tests
# ============================================================

class {Resource}CRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('{app}:{resource}-list')
        self.form_options_create_url = reverse('{app}:{resource}-form-options-create')
        self.form_options_update_url = reverse('{app}:{resource}-form-options-update')

    def _detail_url(self, resource):
        return reverse('{app}:{resource}-detail', args=[resource.id])

    def _payload(self, **overrides):
        data = {Resource}Factory.build()
        payload = {'{field1}': data.{field1}, '{field2}': data.{field2}}
        payload.update(overrides)
        return payload

    def test_list_resources(self):
        {Resource}Factory.create_batch(size=5, organization=self.organization)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 5)

    def test_list_only_active(self):
        {Resource}Factory(organization=self.organization, is_active=False)
        {Resource}Factory(organization=self.organization)
        response = self.client.get(self.list_url)
        for result in response.data['results']:
            self.assertTrue(result['is_active'])

    def test_create_resource(self):
        payload = self._payload()
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_retrieve_resource(self):
        resource = {Resource}Factory(organization=self.organization)
        response = self.client.get(self._detail_url(resource))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_nonexistent(self):
        response = self.client.get(self._detail_url({Resource}Factory.build(id=99999)))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_resource(self):
        resource = {Resource}Factory(organization=self.organization)
        response = self.client.delete(self._detail_url(resource))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_soft_delete(self):
        resource = {Resource}Factory(organization=self.organization)
        self.client.delete(self._detail_url(resource))
        resource.refresh_from_db()
        self.assertFalse(resource.is_active)

    def test_delete_removes_from_list(self):
        resource = {Resource}Factory(organization=self.organization)
        self.client.delete(self._detail_url(resource))
        response = self.client.get(self.list_url)
        for result in response.data['results']:
            self.assertNotEqual(result['id'], resource.id)

    def test_form_options_create(self):
        response = self.client.get(self.form_options_create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {create_option_fields})

    def test_form_options_update(self):
        response = self.client.get(self.form_options_update_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {update_option_fields})

    def test_form_options_choice_shape(self):
        response = self.client.get(self.form_options_create_url)
        self.assertEqual(
            response.data['{choice_field}'],
            [
                {'value': value, 'label': str(label)}
                for value, label in {Resource}Choices.choices
            ],
        )

    def test_form_options_relation_shape(self):
        response = self.client.get(self.form_options_create_url)
        self.assertEqual(
            set(response.data['{relation_field}']),
            {'count', 'num_pages', 'page_number', 'results'},
        )


# ============================================================
# test_permission.py — Permission matrix tests
# ============================================================

from apps.accounts.tests.permission_matrix import (  # noqa: E402
    ADMIN, ANONYMOUS, INACTIVE, MANAGER, MEMBER, OTHER_ORGANIZATION, OWNER,
    Action, PermissionMatrixMixin,
)

LIST = reverse('{app}:{resource}-list')


def _detail(case):
    resource = {Resource}Factory(organization=case.organization)
    return reverse('{app}:{resource}-detail', args=[resource.pk])


def _payload(case):
    data = {Resource}Factory.build()
    return {'{field1}': data.{field1}, '{field2}': data.{field2}}


class {Resource}PermissionMatrixTestCase(
    PermissionMatrixMixin, APITestCaseMixin, APITestCase
):
    actions = {
        'list': Action('get', lambda case: LIST),
        'retrieve': Action('get', _detail),
        'create': Action('post', lambda case: LIST, _payload),
        'update': Action('put', _detail, _payload),
        'delete': Action('delete', _detail),
    }
    matrix = {
        ANONYMOUS: {'list': 401, 'retrieve': 401, 'create': 401, 'update': 401, 'delete': 401},
        INACTIVE: {'list': 403, 'retrieve': 403, 'create': 403, 'update': 403, 'delete': 403},
        OWNER: {'retrieve': 200, 'create': 201, 'update': 200, 'delete': 204},
        ADMIN: {'retrieve': 200, 'create': 201, 'update': 200, 'delete': 204},
        MANAGER: {'retrieve': 200, 'create': 403, 'update': 403, 'delete': 403},
        MEMBER: {'retrieve': 200, 'create': 403, 'update': 403, 'delete': 403},
        OTHER_ORGANIZATION: {'retrieve': 404, 'update': 404, 'delete': 404},
    }


# ============================================================
# test_filter.py — Filter field tests
# ============================================================

class {Resource}FilterTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.url = reverse('{app}:{resource}-list')

    def test_filter_{field}_exact(self):
        {Resource}Factory(organization=self.organization, {field}='test-value')
        {Resource}Factory(organization=self.organization, {field}='other-value')
        response = self.client.get(self.url, {'{field}': 'test-value'})
        self.assertEqual(response.data['count'], 1)

    def test_filter_{field}_icontains(self):
        {Resource}Factory(organization=self.organization, {field}='hello world')
        {Resource}Factory(organization=self.organization, {field}='goodbye world')
        response = self.client.get(self.url, {'{field}__icontains': 'hello'})
        self.assertEqual(response.data['count'], 1)


# ============================================================
# test_integration.py — Multi-step flow tests
# ============================================================

class {Resource}IntegrationTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse('{app}:{resource}-list')

    def _detail_url(self, resource):
        return reverse('{app}:{resource}-detail', args=[resource.id])

    def test_create_retrieve_update_delete_flow(self):
        """Full CRUD lifecycle test."""
        # Create
        payload = {Resource}Factory.build().__dict__
        response = self.client.post(self.list_url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        resource_id = response.data['id']

        # Retrieve
        response = self.client.get(reverse('{app}:{resource}-detail', args=[resource_id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Update
        update_payload = {field: 'updated-value'}
        response = self.client.put(reverse('{app}:{resource}-detail', args=[resource_id]), data=update_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Delete
        response = self.client.delete(reverse('{app}:{resource}-detail', args=[resource_id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify soft-delete
        response = self.client.get(reverse('{app}:{resource}-detail', args=[resource_id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
