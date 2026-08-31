---
name: scaffold-resource
description: >
  Use to scaffold a complete new Django resource following the 12-step checklist.
  Generates model, manager, choices, serializer, filter, permission, viewset,
  factory, URL registration, tests, and migration. Phased approach with
  confirmation between each step.
metadata:
  author: crewforge
  version: "1.0"
  risk: critical
  type: user-invoked
---

# Scaffold Resource — Complete Django Resource Generator

You will act as a **Django Backend Architect** specialized in generating complete REST API resources following the CrewForge 12-step checklist.

Your responsibility is to generate all files needed for a new API resource, following the exact patterns in `docs/architecture.md`, `docs/patterns/`, and existing resources.

---

## Prerequisite: Contextualization

Before generating, read:

1. `AGENTS.md` — Non-Negotiable Rules, MRO, naming conventions
2. `docs/architecture.md` — 12-step checklist, code organization
3. `docs/patterns/structural-patterns.md` — Mixin patterns
4. `docs/patterns/behavioral-patterns.md` — Template Method, Strategy
5. `docs/patterns/creational-patterns.md` — Factory patterns
6. `docs/patterns/test-patterns.md` — Test infrastructure
7. `apps/accounts/models/` — existing model patterns
8. `apps/accounts/viewsets/` — existing viewset patterns
9. `apps/accounts/factories/` — existing factory patterns

---

## Workflow

### Phase 1 — GRILLING Level 1 (Essential — 5 questions)

Before generating ANY code, you MUST ask these essential questions:

```
Resource Configuration (Essential):

1. Resource name: [ex: Project]
2. App destination: [ex: teams]
3. Fields (name, type):
   - name: [type] (e.g., CharField, TextField, BooleanField)
   - [list all fields with basic types]
4. Permissions:
   - Read: [all authenticated / specific roles]
   - Create: [minimum role: owner/admin/manager/member]
   - Update: [minimum role]
   - Delete: [minimum role]
5. TDD mode? [yes/no — generate tests before implementation]
```

Wait for ALL answers before proceeding. Then ask:

### Phase 1.5 — GRILLING Level 2 (Detailed — 7 questions, Optional)

Do you want full control over all configuration options? [yes/no]

If yes:

```
Resource Configuration (Detailed):

6. Relationships:
   - FK to [model] (on_delete=..., related_name=...)
   - OneToOne to [model]
   - M2M to [model] (if applicable)
7. Choices enum needed? [yes/no]
   - If yes, list choices: [CHOICE1, CHOICE2, ...]
8. Custom actions beyond CRUD? [list or none]
9. Hard-delete? [yes/no — default: no (soft-delete)]
10. organization_filter: [default: 'organization_id' / custom: 'team__organization_id']
11. Serializer nesting: [any nested read serializers?]
12. Filter fields: [list fields with lookups]
13. Unique constraints: [list unique_together or UniqueConstraint fields]
```

If no, use sensible defaults:
- Relationships: Infer from field names (e.g., `team_id` → FK to Team)
- Choices: No
- Custom actions: None
- Hard-delete: No
- organization_filter: Default
- Serializer nesting: No
- Filter fields: Name only
- Unique constraints: None

Wait for confirmation before proceeding.

### TDD Mode Workflow

If TDD mode is enabled (question 5 = yes), reorder phases:

**Standard Mode** (TDD = no):
1. Phase 2: Model + Manager + Choices
2. Phase 3: Serializer + Filter
3. Phase 4: Permission
4. Phase 5: ViewSet + URL
5. Phase 6: Factory
6. Phase 7: Tests
7. Phase 8: Migration + Schema
8. Phase 9: Quality Gates

**TDD Mode** (TDD = yes):
1. Phase 2: Tests (skeleton only — Red phase)
2. User implements code
3. Phase 3: Model + Manager + Choices
4. Phase 4: Serializer + Filter
5. Phase 5: Permission
6. Phase 6: ViewSet + URL
7. Phase 7: Factory
8. Phase 8: Tests (fill in remaining — Green phase)
9. Phase 9: Migration + Schema
10. Phase 10: Quality Gates

In TDD mode, delegate to `scaffold-test-matrix` with TDD flag:
- First call: Generate test skeletons only
- Second call: Fill in remaining tests after implementation

### Phase 2 — Model + Manager + Choices

Generate and present:

1. `apps/{app}/models/{resource}.py` — Model with BaseModel, fields, verbose_name, help_text, `__str__`, Meta
2. `apps/{app}/managers/{resource}.py` — Manager with cascading filter_actives if FK to active entity
3. `apps/{app}/choices.py` — Choice enum (if needed)

Show the code. Wait for confirmation.

### Phase 3 — Serializer + Filter

Generate and present:

1. `apps/{app}/serializers/{resource}.py` — Serializer with ModelSerializerMixin
2. `apps/{app}/filters.py` — Filter with FilterSetMixin

Show the code. Wait for confirmation.

### Phase 4 — Permission

Delegate to `scaffold-permission` skill or generate inline.

Show the code. Wait for confirmation.

### Phase 5 — ViewSet + URL

Generate and present:

1. `apps/{app}/viewsets/{resource}.py` — ViewSet with MRO, @extend_schema_model_view_set, label_expression
2. `apps/{app}/urls.py` — URL registration with DefaultRouter

Show the code. Wait for confirmation.

### Phase 6 — Factory

Generate and present:

1. `apps/{app}/factories/{resource}.py` — Factory with ModelFactoryMixin, SubFactory, traits

Show the code. Wait for confirmation.

### Phase 7 — Tests

Delegate to `scaffold-test-matrix` skill or generate inline.

Show the test files. Wait for confirmation.

### Phase 8 — Migration + Schema

1. Run `make makemigrations`
2. Run `make l_spectacular` (if schema changed)
3. Report results

### Phase 9 — Quality Gates (Mandatory)

Run sequentially and report results:

1. `make l_format_code` — lint + format
2. `make l_test` — full test suite
3. `make l_spectacular` — OpenAPI schema (if API changed)

If any gate fails, fix issues before reporting success.

---

## Reference Templates

See `references/model-template.py`, `references/viewset-template.py`, `references/factory-template.py`, `references/url-template.py` for exact patterns.

---

## Anti-patterns

- **Do not skip the grilling phase.** Essential questions must be answered before generating code
- **Do not generate code in one shot.** Each phase must be confirmed before proceeding
- **Do not skip `super().has_object_permission()` in permissions.** Organization scope is mandatory
- **Do not forget `@extend_schema_model_view_set` decorator.** Required for OpenAPI schema
- **Do not forget `label_expression` or `value_expression` on ViewSet.** Required for choices endpoint
- **Do not forget barrel exports.** Models `__init__.py`, serializers, factories must be importable
- **Do not use `related_name='+'` for FK fields that need reverse access.** Use meaningful related_names
- **Do not skip quality gates.** All 3 must pass before considering work complete
- **Do not commit if tests fail.** Fix issues first
- **Do not ask all 13 questions by default.** Start with Level 1 (5 essential), offer Level 2 if needed

---

## Generated Output Example

### Input (GRILLING answers)
- Resource: Project
- App: teams
- Fields: name (CharField, max_length=100), description (TextField, null=True)
- Permissions: Read: all, Create: manager+

### Output (Phase 2 excerpt)
```python
# apps/teams/models/project.py

from django.db import models

from apps.generics.models import BaseModel


class Project(BaseModel):
    name = models.CharField(max_length=100, verbose_name="Project name")
    description = models.TextField(null=True, blank=True, verbose_name="Description")
    team = models.ForeignKey(
        "teams.Team",
        on_delete=models.CASCADE,
        related_name="projects",
        verbose_name="Team",
    )

    class Meta:
        verbose_name = "project"
        verbose_name_plural = "projects"

    def __str__(self):
        return self.name
```

### Output (Phase 5 excerpt)
```python
# apps/teams/viewsets/project.py

from rest_framework import viewsets
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.generics.viewsets import ModelViewSetMixin
from apps.accounts.viewsets.mixins import OrganizationScopedViewSetMixin

from ..models.project import Project
from ..serializers.project import ProjectSerializer
from ..permissions import ProjectPermission


@extend_schema_view(
    list=extend_schema(tags=["Projects"]),
    create=extend_schema(tags=["Projects"]),
    retrieve=extend_schema(tags=["Projects"]),
    update=extend_schema(tags=["Projects"]),
    partial_update=extend_schema(tags=["Projects"]),
    destroy=extend_schema(tags=["Projects"]),
)
class ProjectViewSet(OrganizationScopedViewSetMixin, ModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Project.objects.filter_actives()
    serializer_class = ProjectSerializer
    permission_classes = [ProjectPermission]
    label_expression = "name"
```
