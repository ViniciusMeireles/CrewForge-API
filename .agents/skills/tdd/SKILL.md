---
name: tdd
description: >
  Test-driven development with red-green-refactor loop.
  Use when implementing new features or fixing bugs.
  Writes failing test first, then implements minimum code to pass.
metadata:
  author: crewforge
  version: "1.0"
  risk: safe
  type: model-invoked
---

# TDD — Red-Green-Refactor

You will act as a **QA Engineer** enforcing test-driven development discipline.

Your responsibility is to guide the implementation through a strict red-green-refactor cycle, ensuring tests are written before code.

---

## Prerequisite: Contextualization

Before starting, read:

1. `docs/patterns/test-patterns.md` — test infrastructure, naming, patterns
2. `docs/quality.md` — coverage matrix and grading
3. `apps/accounts/tests/mixins.py` — APITestCaseMixin
4. `apps/accounts/tests/client.py` — CustomAPIClient

---

## Workflow

### Step 1: Understand Requirement

Ask the user:

```
Feature Configuration:

1. What is the feature? [describe behavior]
2. Resource name: [ex: Project]
3. App: [ex: teams]
4. Expected behavior:
   - Input: [what triggers the behavior]
   - Output: [what should happen]
   - Edge cases: [list any]
```

Wait for answers before proceeding.

### Step 2: Red (Failing Test)

1. Write a minimal test that expresses the expected behavior
2. Use the smallest possible assertion
3. Run `make l_test_fast` to confirm it fails
4. Show the failing test to the user

**Example**:
```python
# apps/teams/tests/test_project/test_crud.py

class ProjectCreateTestCase(APITestCaseMixin, APITestCase):
    def test_create_project_requires_name(self):
        """Test create without name returns 400."""
        payload = {}  # missing name
        response = self.client.post(self.list_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
```

**Run**:
```bash
make l_test_fast
```

**Expected**: Test fails with assertion error.

### Step 3: Green (Passing Test)

1. Write the minimum code to make the test pass
2. Do not add extra functionality
3. Run `make l_test_fast` to confirm it passes
4. Show the passing implementation

**Example**:
```python
# apps/teams/serializers/project.py

class ProjectSerializer(ModelSerializerMixin):
    class Meta:
        model = Project
        fields = ["id", "name", "description"]
        extra_kwargs = {
            "name": {"required": True},
        }
```

**Run**:
```bash
make l_test_fast
```

**Expected**: Test passes.

### Step 4: Refactor

1. Improve code structure without changing behavior
2. Extract methods, rename variables, improve readability
3. Run `make l_test_fast` to confirm still passing
4. Show the refactored code

**Example**:
```python
# Refactored: added help_text, verbose_name
class ProjectSerializer(ModelSerializerMixin):
    class Meta:
        model = Project
        fields = ["id", "name", "description"]
        extra_kwargs = {
            "name": {
                "required": True,
                "help_text": "Project name",
            },
            "description": {
                "required": False,
                "help_text": "Project description",
            },
        }
```

### Step 5: Commit

1. Run `make l_format_code`
2. Run `make l_test` (full suite)
3. Commit with message: `✨ feat: {description}`

---

## Anti-patterns

- **Do not skip Red phase.** Test must fail before implementation
- **Do not write more than needed for Green.** Minimal implementation
- **Do not refactor during Green.** Only in Refactor phase
- **Do not skip tests.** Every feature needs tests
- **Do not forget to run full suite before commit.** Ensure no regressions
- **Do not write multiple tests at once.** One test per cycle

---

## Integration with scaffold-test-matrix

When used with `scaffold-test-matrix`, the TDD skill can:

1. Generate test skeletons first (Red phase)
2. User implements code
3. Fill in remaining tests (Green phase)
4. Refactor all tests together

This approach ensures tests drive the implementation, not the other way around.
