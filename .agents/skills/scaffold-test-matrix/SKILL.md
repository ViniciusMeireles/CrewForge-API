---
name: scaffold-test-matrix
description: >
  Use to generate the 8 test files for a new Django resource, covering the
  19-scenario coverage matrix. Called by scaffold-resource or standalone.
  Generates test_model, test_serializer, test_crud, test_permission,
  test_filter, test_choices, test_integration, and __init__.py.
metadata:
  author: crewforge
  version: "1.0"
  risk: safe
  type: user-invoked
---

# Scaffold Test Matrix — Test Suite Generator

You will act as a **QA Engineer** specialized in Django REST Framework test suites.

Your responsibility is to generate 8 test files covering the 19-scenario coverage matrix defined in `docs/quality.md` and `docs/patterns/test-patterns.md`.

---

## Prerequisite: Contextualization

Before generating, read:

1. `docs/patterns/test-patterns.md` — test infrastructure, naming, patterns
2. `docs/quality.md` — coverage matrix and grading
3. `apps/accounts/tests/client.py` — CustomAPIClient
4. `apps/accounts/tests/mixins.py` — APITestCaseMixin
5. An existing test directory (e.g., `apps/teams/tests/test_team/`) as reference

---

## Workflow

### Phase 1 — Gather Requirements (Essential)

Ask the user:

```
Test Configuration (Essential):

1. Resource name: [ex: Team]
2. App: [ex: teams]
3. Fields to test:
   - [x] name (CharField, required)
   - [ ] description (TextField, optional)
4. Coverage mode: [essential (4 files) / full (8 files)]
```

Wait for answers. Then ask:

### Phase 1.5 — Full Configuration (Optional)

Do you want full coverage with all 8 test files? [yes/no]

If yes:

```
Test Configuration (Full):

5. Serializer class: [ex: TeamSerializer]
6. Permission class: [ex: TeamPermission]
7. Filter class: [ex: TeamFilter]
8. Factory class: [ex: TeamFactory]
9. URL basename: [ex: teams]
10. Custom actions: [none / list them]
11. Role hierarchy for permissions:
    - Read: [all members / specific roles]
    - Create: [minimum role]
    - Update: [minimum role]
    - Delete: [minimum role]
```

If no, use essential mode:
- Generate only: test_model, test_crud, test_permission, test_choices
- Infer classes from resource name
- Default role hierarchy: Read all, Write manager+

### Coverage Modes

| Mode | Files | Scenarios | When to use |
|------|-------|-----------|-------------|
| **Essential** | 4 files | 12 scenarios | Quick scaffolding, MVPs |
| **Full** | 8 files | 19 scenarios | Production-ready resources |

Essential mode generates:
- `test_model.py` — Model behavior
- `test_crud.py` — CRUD operations
- `test_permission.py` — Permission matrix
- `test_choices.py` — Choice enums

Full mode adds:
- `test_serializer.py` — Field contracts
- `test_filter.py` — Filter fields
- `test_integration.py` — Multi-step flows
- `__init__.py` — Package init

### TDD Mode (Optional)

If user selected TDD mode in scaffold-resource, or wants TDD:

1. Generate only test skeletons with failing assertions
2. User implements code
3. Return to fill in remaining tests

**TDD Skeleton Example**:
```python
# apps/teams/tests/test_project/test_crud.py

class ProjectCRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse("teams:project-list")

    def test_create_project(self):
        """Test create returns 201."""
        payload = {"name": "Test"}  # TODO: implement serializer
        response = self.client.post(self.list_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)  # Will fail
```

Run `make l_test_fast` to confirm failure, then implement code.

### Phase 2 — Generate Files (Phase by Phase)

Generate files one at a time, presenting each for confirmation before moving to the next.

#### Phase 2a: test_model.py + test_choices.py

Present the model and choices tests. These test:
- `__str__` method
- `label_expression` (if exists)
- `filter_actives` / `filter_inactives`
- `get_or_none`
- Unique constraints
- Choice enum values and labels

Wait for confirmation.

#### Phase 2b: test_serializer.py

Present the serializer tests. These test:
- Field contracts (list vs detail response)
- Validation errors (required fields, unique constraints)
- Auto-populated fields (created_by, updated_by, organization)

Wait for confirmation.

#### Phase 2c: test_crud.py

Present the CRUD tests. These test:
- List (200, pagination)
- Create (201)
- Retrieve (200)
- Update (200)
- Delete (204, soft-delete)
- List excludes soft-deleted
- Choices endpoint (200)

Wait for confirmation.

#### Phase 2d: test_permission.py

Present the permission tests. These test:
- Unauthenticated for all endpoints (401)
- Inactive member for all actions (403)
- Role hierarchy write checks
- All roles can read
- Cross-org write (403/404)
- Cross-org read (filtered)

Wait for confirmation.

#### Phase 2e: test_filter.py

Present the filter tests. These test:
- Each filter field individually
- Combined filters
- Filter with no results

Wait for confirmation.

#### Phase 2f: test_integration.py

Present the integration tests. These test:
- Multi-step flow (create → retrieve → update → delete)
- Edge cases specific to the resource

Wait for confirmation.

### Phase 3 — Write All Files

Create directory `apps/{app}/tests/test_{resource}/` and write all 8 files.

---

## Anti-patterns

- **Do not skip test_permission.py.** It's the most critical test file
- **Do not test implementation details.** Only test public interfaces (HTTP, model methods)
- **Do not forget `self.new_account()` setup.** Every test class needs organization context
- **Do not hardcode IDs.** Always use factory-created objects
- **Do not skip the 404 test for detail endpoints.** Verify nonexistent object returns 404

---

## Test File Example

### Input
- Resource: Project
- Fields: name (required), description (optional)

### Output (test_crud.py excerpt)
```python
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.tests.mixins import APITestCaseMixin
from apps.teams.factories import ProjectFactory


class ProjectCRUDTestCase(APITestCaseMixin, APITestCase):
    def setUp(self):
        self.organization = self.new_account()
        self.list_url = reverse("teams:project-list")

    def _detail_url(self, project):
        return reverse("teams:project-detail", args=[project.id])

    def test_list_projects(self):
        """Test list returns 200 with pagination."""
        ProjectFactory(organization=self.organization)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_create_project(self):
        """Test create returns 201."""
        payload = {"name": "New Project"}
        response = self.client.post(self.list_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Project")

    def test_retrieve_project(self):
        """Test retrieve returns 200."""
        project = ProjectFactory(organization=self.organization)
        response = self.client.get(self._detail_url(project))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_project(self):
        """Test update returns 200."""
        project = ProjectFactory(organization=self.organization)
        payload = {"name": "Updated Name"}
        response = self.client.put(self._detail_url(project), payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_project(self):
        """Test delete returns 204 (soft-delete)."""
        project = ProjectFactory(organization=self.organization)
        response = self.client.delete(self._detail_url(project))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Verify soft-delete
        project.refresh_from_db()
        self.assertFalse(project.is_active)
```
