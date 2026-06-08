# Test Patterns

This document describes the canonical test structure and conventions for
CrewForge API tests.

---

## Table of Contents

- [Rationale](#rationale)
- [Directory Structure](#directory-structure)
- [Test File Categories](#test-file-categories)
- [Naming Conventions](#naming-conventions)
- [Test Infrastructure](#test-infrastructure)
- [Setup Patterns](#setup-patterns)
- [Helper Patterns](#helper-patterns)
- [Assertion Patterns](#assertion-patterns)
- [Factory Patterns](#factory-patterns)
- [Coverage Matrix](#coverage-matrix)
- [Reference Implementations](#reference-implementations)

---

## Rationale

Older tests used a single flat file per resource (e.g., `test_members.py`) with
one monolithic test class. This became hard to navigate as test counts grew.

The current standard — inspired by `StoredFile` and `OrganizationImage` — uses a
**dedicated test directory** with one file per concern. This provides:

- Single responsibility per test file
- Faster navigation (open only the file relevant to the bug)
- Clear separation of model, serializer, CRUD, permission, and integration tests
- Easy parallel test execution

---

## Directory Structure

Every new resource `{resource}` gets a test directory:

```
apps/{app}/tests/test_{resource}/
├── __init__.py
├── test_model.py
├── test_serializer.py
├── test_crud.py
├── test_permission.py
├── test_filter.py
├── test_choices.py
└── test_integration.py
```

Resource-specific behavior may add extra files (e.g.,
`test_download.py` for `StoredFile`).

---

## Test File Categories

### `test_model.py`

Tests model-level behavior — no HTTP, no API client. Uses plain `TestCase`
(faster, no request factory setup).

**What to test:**
- `__str__` output
- `label_expression` (if applicable)
- `filter_actives()` — all active, self inactive, each FK inactive
- `filter_inactives()`
- `get_or_none()` — found and not found
- Unique constraints (DB-level via `IntegrityError`)
- Cascade deletes
- Default field values
- Ordering

**Standard imports:**
```python
from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.factories.organization_image import OrganizationImageFactory
from apps.accounts.factories.organizations import OrganizationProfileFactory
```

---

### `test_serializer.py`

Tests serializer field contracts, validation, and auto-populated fields.

**What to test:**
- List serializer field set (exact keys via `set(result.keys())`)
- Detail serializer field set
- Read-only fields ignored on create (`id`, `is_active`, `created_at`, etc.)
- Validation: duplicate values, missing required fields, invalid values
- Auto-populated fields (`created_by`, `updated_by`, `organization`, `profile`)
- Nested serializer output
- Create/update behavior for all variants

**Standard imports:**
```python
from rest_framework import status as http_status
from apps.accounts.tests.mixins import APITestCaseMixin
```

---

### `test_crud.py`

Tests HTTP CRUD operations via the API.

**What to test:**
- `test_list_{resource}` — list returns expected count
- `test_list_only_active` — soft-deleted excluded from list
- `test_create_{resource}` — basic create, verify response data
- `test_create_{resource}_default_{field}` — default field values
- `test_retrieve_{resource}` — detail endpoint
- `test_retrieve_nonexistent` — 404
- `test_update_{resource}_full` — full PUT update
- `test_partial_update_{field}` — PATCH, one field at a time
- `test_delete_{resource}` — delete, soft-delete verification
- `test_delete_removes_from_list` — deleted not in list
- `test_delete_nonexistent` — 404
- `test_create_duplicate_{field}` — 400
- `test_create_all_{variants}` — all type/permission variants
- `test_choices_endpoint` — choices returns value/label pairs

**Standard imports:**
```python
import tempfile

from django.test import override_settings
from rest_framework import status as http_status

from apps.accounts.tests.mixins import APITestCaseMixin
```

---

### `test_permission.py`

Tests the full permission matrix: authentication, role hierarchy, inactive
members, and cross-org isolation.

**What to test (every endpoint action):**

| Scenario | Pattern | Expected |
|----------|---------|----------|
| Unauthenticated | `test_not_authenticated_{action}` | 401 |
| Inactive member | `test_not_active_member_{action}` | 403 |
| Owner write | `test_owner_can_{action}` | 200/204 |
| Admin write | `test_admin_can_{action}` | 200/204 |
| Manager write | `test_manager_cannot_{action}` | 403 |
| Member write | `test_member_cannot_{action}` | 403 |
| All roles read | `test_{role}_can_retrieve` | 200 |
| Cross-org write | `test_cross_org_member_{action}` | 403/404 |
| Cross-org read | `test_cross_org_member_retrieve` | 200/404 |

**Key conventions:**
- Create a fresh resource in `setUp` or per-test for isolation
- `force_authenticate(member=member)` for each role switch
- Cross-org tests use `MemberFactory` with a different organization

**Standard imports:**
```python
import tempfile

from django.test import override_settings
from rest_framework import status as http_status

from apps.accounts.choices import MemberRoleChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organization_image import OrganizationImageFactory
from apps.accounts.tests.mixins import APITestCaseMixin
```

---

### `test_filter.py`

Tests django-filter FilterSet fields.

**What to test:**
- Each filter field with an exact match
- `icontains` / `__in` lookups where applicable
- Combined filters (multiple fields at once)
- `is_active` filter (if exposed)

**Standard imports:**
```python
from rest_framework import status as http_status

from apps.accounts.factories.organization_image import OrganizationImageFactory
from apps.accounts.tests.mixins import APITestCaseMixin
```

---

### `test_choices.py`

Tests choice enum values and labels.

**What to test:**
- `test_enum_values_count` — correct number of choices
- `test_enum_values` — each value string matches expected
- `test_enum_labels` — each label matches expected

**Standard imports:**
```python
from django.test import TestCase

from apps.accounts.choices import OrganizationImageTypeChoices
```

---

### `test_integration.py`

Tests multi-step flows that combine several operations.

**What to test:**
- Full CRUD flow: create → list → retrieve → update → delete → verify gone
- Permission hierarchy read access (all roles can read)
- Permission hierarchy write access (matrix: role × expected status)
- "Create then choices reflects" — verify choices endpoint after creation

**Standard imports:**
```python
import tempfile

from django.test import override_settings
from rest_framework import status as http_status

from apps.accounts.choices import MemberRoleChoices, OrganizationImageTypeChoices
from apps.accounts.factories.members import MemberFactory
from apps.accounts.factories.organization_image import OrganizationImageFactory
from apps.accounts.tests.mixins import APITestCaseMixin
```

---

## Naming Conventions

### File names

```
test_{resource}.py                   # flat (legacy, avoid for new resources)
test_{resource}/                     # directory (current standard)
test_{resource}/__init__.py          # empty
test_{resource}/test_model.py
test_{resource}/test_serializer.py
test_{resource}/test_crud.py
test_{resource}/test_permission.py
test_{resource}/test_filter.py
test_{resource}/test_choices.py
test_{resource}/test_integration.py
```

### Class names

```
{Resource}{Category}TestCase
```

Examples:

| File | Class |
|------|-------|
| `test_model.py` | `OrganizationImageModelTestCase` |
| `test_serializer.py` | `OrganizationImageSerializerTestCase` |
| `test_crud.py` | `OrganizationImageCRUDTestCase` |
| `test_permission.py` | `OrganizationImagePermissionTestCase` |
| `test_filter.py` | `OrganizationImageFilterTestCase` |
| `test_choices.py` | `OrganizationImageTypeChoicesTestCase` |
| `test_integration.py` | `OrganizationImageIntegrationTestCase` |

### Method names

Use the `test_{scenario}` pattern without docstrings:

```
test_create_{resource}
test_retrieve_{resource}
test_list_{resource}
test_update_{resource}
test_delete_{resource}
test_list_only_active
test_create_duplicate_{field}
test_retrieve_nonexistent
test_delete_nonexistent
test_delete_removes_from_list
test_create_all_{variants}

test_not_authenticated_{action}
test_not_active_member_{action}

test_owner_can_{action}
test_admin_can_{action}
test_manager_cannot_{action}
test_member_cannot_{action}

test_{role}_can_retrieve

test_cross_org_member_{action}
```

Avoid docstrings — the method name should be descriptive enough.

---

## Test Infrastructure

### Base Classes

| Class | When to use | Location |
|-------|-------------|----------|
| `TestCase` | Model tests (`test_model.py`), choices tests (`test_choices.py`) | `django.test.TestCase` |
| `APITestCase` + `APITestCaseMixin` | Serializer, CRUD, permission, filter, integration tests | `rest_framework.test.APITestCase` + `apps.accounts.tests.mixins.APITestCaseMixin` |

### CustomAPIClient

`APITestCaseMixin` sets `client_class = CustomAPIClient`. The client's
`force_authenticate(member=member)` performs both JWT auth and organization
login (step 3 of the auth flow), setting `request.session['organization_id']`.

Always use `force_authenticate(member=member)` instead of
`force_authenticate(user=user)` to ensure organization context is established.

### @override_settings

Use `@override_settings(MEDIA_ROOT=tempfile.mkdtemp())` on any test class that
creates files via the API. This prevents test artifacts from polluting the
real media directory.

```python
import tempfile

from django.test import override_settings

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OrganizationImageSerializerTestCase(APITestCaseMixin, APITestCase):
    ...
```

---

## Setup Patterns

### Model tests (TestCase)

```python
class OrganizationImageModelTestCase(TestCase):
    def test_str(self):
        image = OrganizationImageFactory()
        self.assertEqual(
            str(image), f'{image.profile} - {image.image_type}'
        )
```

### API tests (APITestCase + APITestCaseMixin)

```python
class OrganizationImageCRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.profile = self.organization.get_profile()
        self.list_url = reverse('accounts:organization_images-list')
```

### Anonymous/unauthenticated tests

```python
def test_not_authenticated_list(self):
    self.client.logout()
    response = self.client.get(self.list_url)
    self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
```

Or:

```python
self.client.force_authenticate(user=None)
```

---

## Helper Patterns

### Payload helper with `**overrides`

Build a base payload, then apply test-specific overrides:

```python
def _image_payload(self, **overrides):
    payload = {
        'image_type': OrganizationImageTypeChoices.LOGO,
        'image.file': SimpleUploadedFile(
            name='test.png',
            content=b'fake-image-content',
            content_type='image/png',
        ),
    }
    payload.update(overrides)
    return payload
```

Usage:

```python
def test_create_image(self):
    payload = self._image_payload(image_type=OrganizationImageTypeChoices.COVER)
    response = self.client.post(self.list_url, data=payload, format='multipart')
    self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
```

### Detail URL helper

```python
def _detail_url(self, image):
    return reverse(
        'accounts:organization_images-detail',
        kwargs={'pk': image.pk},
    )
```

### Resource creation helper

```python
def _create_image(self, **kwargs):
    return OrganizationImageFactory(profile=self.profile, **kwargs)
```

---

## Assertion Patterns

### Status codes

```python
self.assertEqual(response.status_code, http_status.HTTP_200_OK)   # list, retrieve, update
self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)  # create
self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)  # delete
self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)  # validation
self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)  # auth
self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)  # permission
self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)  # not found
```

### Field contract verification

Use `set()` and `keys()` to verify exact fields returned:

```python
def test_list_serializer_fields(self):
    response = self.client.get(self.list_url)
    self.assertEqual(response.status_code, http_status.HTTP_200_OK)
    self.assertEqual(
        set(response.data['results'][0].keys()),
        {'id', 'image_type', 'image'},
    )
```

```python
def test_detail_serializer_fields(self):
    url = self._detail_url(self.image)
    response = self.client.get(url)
    self.assertEqual(response.status_code, http_status.HTTP_200_OK)
    self.assertEqual(
        set(response.data.keys()),
        {
            'id', 'image_type', 'image', 'is_active',
            'created_at', 'updated_at',
            'created_by', 'updated_by',
        },
    )
```

### Soft-delete verification

Use `refresh_from_db()` instead of re-fetching from the API:

```python
def test_delete_soft_delete(self):
    response = self.client.delete(self._detail_url(self.image))
    self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
    self.image.refresh_from_db()
    self.assertFalse(self.image.is_active)
```

### DB-level unique constraint

```python
def test_unique_constraint_same_profile_and_type(self):
    profile = OrganizationProfileFactory()
    OrganizationImageFactory(profile=profile, image_type=OrganizationImageTypeChoices.LOGO)
    with self.assertRaises(IntegrityError):
        OrganizationImageFactory(profile=profile, image_type=OrganizationImageTypeChoices.LOGO)
```

---

## Factory Patterns

### All factories

All factories extend `ModelFactoryMixin` and `DjangoModelFactory`:

```python
class OrganizationImageFactory(ModelFactoryMixin, DjangoModelFactory):
    profile = factory.SubFactory(OrganizationProfileFactory)
    image = factory.SubFactory(
        'apps.accounts.factories.files.StoredFileFactory',
        public=True,
    )
    image_type = OrganizationImageTypeChoices.LOGO

    class Meta:
        model = OrganizationImage
```

### Traits

Use `factory.Trait` (via inner `Params` class) for named scenario variations:

```python
class StoredFileFactory(ModelFactoryMixin, DjangoModelFactory):
    class Params:
        pdf = factory.Trait(
            file=factory.django.FileField(
                filename='test.pdf',
                data=b'%PDF-1.4 fake pdf content',
            ),
        )
        public = factory.Trait(
            viewing_permission=StoredFileAccess.PUBLIC,
        )
```

Usage:

```python
StoredFileFactory(pdf=True, public=True)
```

### Context propagation

Use `SelfAttribute` to propagate shared context (e.g., same organization):

```python
class TeamMemberFactory(ModelFactoryMixin, DjangoModelFactory):
    class Params:
        organization = factory.SubFactory(OrganizationFactory)

    team = factory.SubFactory(
        'apps.teams.factories.teams.TeamFactory',
        organization=factory.SelfAttribute('..organization'),
    )
    member = factory.SubFactory(
        'apps.accounts.factories.members.MemberFactory',
        organization=factory.SelfAttribute('..organization'),
    )
```

---

## Coverage Matrix

Every new resource's test suite must cover:

| # | Scenario | Expected | File |
|---|----------|----------|------|
| 1 | Happy path CRUD (create, list, retrieve, update, delete) | 200/201/204 | `test_crud.py` |
| 2 | List excludes soft-deleted | Only active returned | `test_crud.py` |
| 3 | Unauthenticated for all endpoints | 401 | `test_permission.py` |
| 4 | Inactive member for all actions | 403 | `test_permission.py` |
| 5 | Role hierarchy write (owner/admin can, manager/member cannot) | 200/403 | `test_permission.py` |
| 6 | All roles can read | 200 | `test_permission.py` |
| 7 | Cross-org write returns 403/404 | 403/404 | `test_permission.py` |
| 8 | Cross-org read returns 200/404 | 200/404 | `test_permission.py` |
| 9 | Model properties (`__str__`, manager methods, constraints) | — | `test_model.py` |
| 10 | Serializer field contracts (list vs detail) | Exact key sets | `test_serializer.py` |
| 11 | Validation errors (duplicates, missing fields) | 400 | `test_serializer.py` |
| 12 | Auto-populated fields | Set from auth context | `test_serializer.py` |
| 13 | Filter fields | Filtered result set | `test_filter.py` |
| 14 | Choices endpoint | Value/label format | `test_crud.py` + `test_choices.py` |
| 15 | Enum values and labels | Correct strings | `test_choices.py` |
| 16 | Multi-step integration flow | End-to-end | `test_integration.py` |

---

## Reference Implementations

These test directories embody the pattern described here:

- `apps/accounts/tests/test_organization_images/` — Clean example with 8 files,
  92 tests covering model, serializer, CRUD, permission, filter, choices, and
  integration.
- `apps/accounts/tests/test_stored_files/` — Extended example with 9 files
  (adds `test_download.py` for resource-specific behavior), covering model,
  serializer, CRUD, permission, filter, choices, download, and integration.
