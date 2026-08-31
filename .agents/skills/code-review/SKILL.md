---
name: code-review
description: >
  Review generated code against CrewForge standards.
  Use after scaffolding or manual implementation.
  Checks architecture, permissions, tests, and naming conventions.
metadata:
  author: crewforge
  version: "1.0"
  risk: safe
  type: user-invoked
---

# Code Review — Quality Gate

You will act as a **Senior Engineer** reviewing code for quality and compliance with CrewForge standards.

---

## Prerequisite: Contextualization

Before reviewing, read:

1. `AGENTS.md` — Non-Negotiable Rules, MRO, naming conventions
2. `docs/architecture.md` — 12-step checklist, code organization
3. `docs/patterns/behavioral-patterns.md` — Strategy pattern
4. `docs/patterns/test-patterns.md` — Test infrastructure
5. `docs/quality.md` — Coverage matrix and grading

---

## Workflow

### Step 1: Identify Scope

Ask the user:

```
Review Configuration:

1. Resource name: [ex: Project]
2. App: [ex: teams]
3. Files to review: [all / specific files]
```

Wait for answers before proceeding.

### Step 2: Architecture Check

Read and verify:

- [ ] **MRO order**: `OrganizationScopedViewSetMixin` → `ModelViewSetMixin` → `viewsets.ModelViewSet`
- [ ] **Imports from generics**: Use `apps/generics/`, not `apps/accounts/`
- [ ] **Schema decorator**: `@extend_schema_model_view_set` present on ViewSet
- [ ] **Choices endpoint**: `label_expression` or `value_expression` on ViewSet
- [ ] **Barrel exports**: Models `__init__.py`, serializers, factories are importable

### Step 3: Permission Check

Read and verify:

- [ ] **super() called**: `super().has_object_permission()` invoked
- [ ] **get_member used**: `get_member(request)` for member lookup
- [ ] **Role properties**: `has_{role}_permission` used (not hardcoded strings)
- [ ] **Org scope**: `organization_lookup` defined correctly

### Step 4: Test Check

Read and verify:

- [ ] **19 scenarios**: Coverage matrix from `docs/quality.md`
- [ ] **Factories used**: No hardcoded IDs
- [ ] **self.new_account()**: Present in setUp for organization context
- [ ] **Cross-org tests**: Included for permission tests
- [ ] **Soft-delete**: Verify is_active=False after delete

### Step 5: Naming Check

Read and verify:

- [ ] **verbose_name**: On model fields
- [ ] **help_text**: On serializer fields
- [ ] **related_name**: On ForeignKey fields
- [ ] **__str__**: Method on model

### Step 6: Generate Report

Create a checklist with pass/fail for each item:

```markdown
# Code Review Report: {Resource}

## Architecture
- [x] MRO order correct
- [ ] Imports from generics ✗ (uses apps.accounts)
- [x] Schema decorator present
- [x] Choices endpoint defined
- [x] Barrel exports configured

## Permissions
- [x] super() called
- [x] get_member used
- [x] Role properties used
- [x] Org scope enforced

## Tests
- [ ] 19 scenarios ✗ (missing cross-org tests)
- [x] Factories used
- [x] self.new_account() present
- [ ] Cross-org tests ✗ (missing)
- [x] Soft-delete verified

## Naming
- [x] verbose_name present
- [ ] help_text missing on description field
- [x] related_name correct
- [x] __str__ implemented

## Summary
- Passed: 12/15
- Failed: 3
- Action required: Fix missing items before commit
```

### Step 7: Fix Issues (Optional)

If user wants, generate fix instructions for each failed item:

```markdown
## Fix Instructions

### 1. Imports from generics
**File**: `apps/teams/viewsets/project.py`
**Line**: 3
**Current**: `from apps.accounts.viewsets.mixins import OrganizationScopedViewSetMixin`
**Fix**: `from apps.generics.viewsets import OrganizationScopedViewSetMixin`

### 2. Missing cross-org tests
**File**: `apps/teams/tests/test_project/test_permission.py`
**Add**: Test case for cross-org read (filtered) and write (403/404)
```

---

## Anti-patterns

- **Do not skip checks.** All items must be verified
- **Do not approve code with failures.** Fix first
- **Do not check implementation details.** Only public interfaces
- **Do not forget to report.** Summary must be clear and actionable
