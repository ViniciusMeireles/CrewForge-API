# Architecture

This document defines CrewForge's layered architecture, naming conventions,
code organization rules, and complexity guidelines. It is the primary
reference for agents adding or modifying code.

---

## Table of Contents

- [Layered Architecture](#layered-architecture)
- [Data Flow](#data-flow)
- [ViewSet Composition](#viewset-composition)
- [Naming Conventions](#naming-conventions)
- [Code Organization Rules](#code-organization-rules)
- [Complexity Guidelines](#complexity-guidelines)
- [New Resource Checklist](#new-resource-checklist)

---

## Layered Architecture

CrewForge follows a strict layered architecture with clear separation of concerns.

### Layer Stack

```
┌─────────────────────────────────┐
│  Views / ViewSets               │  ← HTTP interface
├─────────────────────────────────┤
│  Permissions                    │  ← Access control
├─────────────────────────────────┤
│  Serializers                    │  ← Validation & serialization
├─────────────────────────────────┤
│  Filters                        │  ← Query filtering
├─────────────────────────────────┤
│  Mixins (accounts)              │  ← Reusable view/serializer/filter behaviors
├─────────────────────────────────┤
│  Models / Managers / QuerySets  │  ← Data layer
├─────────────────────────────────┤
│  Generics (cross-app)           │  ← BaseModel, BaseManager, fields, utils
├─────────────────────────────────┤
│  Database (PostgreSQL)          │  ← Persistence
└─────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Location Pattern | Responsibility |
|-------|-----------------|----------------|
| Views | `apps/*/views/` | HTTP handling, routing, response formatting |
| Permissions | `apps/*/permissions/` | Access control, role-based authorization |
| Serializers | `apps/*/serializers/` | Input validation, output serialization |
| Filters | `apps/*/filters/` | Query parameter filtering via django-filter |
| Mixins | `apps/*/mixins/` | Reusable view/serializer/filter/field behaviors |
| Managers | `apps/*/managers/` | Custom query methods, bulk operations |
| Models | `apps/*/models/` | Domain entities, field definitions, relationships |
| Generics | `apps/generics/` | BaseModel, BaseManager, fields, utils, mails |
| Factories | `apps/*/factories/` | Test data factories (factory-boy) |
| Choices | `apps/*/choices.py` | Enum definitions for roles, permissions, types |
| Fields | `apps/*/fields/` | Custom DRF field classes |
| Emails | `apps/generics/mails/` | EmailBase, CTAEmail, EmailView |
| Settings | `apps/*/settings.py` | App-specific API settings |
| Utils | `apps/generics/utils/` | Schema helpers, serializers, shortcuts, models |

---

## Data Flow

A typical request flows through:

1. **URL Router** → dispatches to the correct ViewSet
2. **ViewSet** → applies `get_queryset()` with organization scoping
3. **Permission** → checks authentication, membership, and role
4. **Filter** → applies query parameter filters
5. **Serializer** → validates input or serializes output
6. **Model/Manager** → executes database operations

All layers depend on the **generics foundation** (`BaseModel`, `BaseManager`,
`BaseQuerySet`, `RequestUserMixin`, `AuthUserFieldMixin`, schema utils, etc.).

---

## ViewSet Composition

### Standard MRO

The most common viewset MRO follows a fixed order with an inherited mixin chain:

```
RequestUserMixin                            (apps/generics/mixins/mixins.py)
  └── OrganizationScopedRequestMixin        (apps/accounts/mixins/requests.py)
        ├── ModelViewSetMixin               (apps/accounts/mixins/views.py)
        └── OrganizationScopedViewSetMixin  (apps/accounts/mixins/views.py)
              │
              └── concrete ViewSet
```

Standard declaration:

```python
class MyViewSet(
    OrganizationScopedViewSetMixin,  # 1st: scope by org
    ModelViewSetMixin,  # 2nd: soft-delete + choices
    viewsets.ModelViewSet,  # 3rd: DRF base
):
    serializer_class = MySerializer
    queryset = MyModel.objects.all()
    permission_classes = [MyPermission]
    filterset_class = MyFilter
    label_expression = 'name'
```

### ViewSet Attributes

| Attribute | Purpose | Example |
|-----------|---------|---------|
| `filter_backends` | DRF filter backends | `[backends.DjangoFilterBackend]` |
| `http_method_names` | Restrict allowed verbs | `['get', 'post']` |
| `base_filters` | Additional fixed filters | `{'is_active': True}` |
| `organization_filter` | FK traversal override | `'team__organization_id'` |
| `lookup_field` | Non-default PK field | `'uuid'` for StoredFile |
| `parser_classes` | Request parsing | `[MultiPartParser, FormParser]` |

### MRO Variations

**Viewsets without `OrganizationScopedViewSetMixin`:**

- `OrganizationViewSet` — uses `ModelViewSetMixin` only (the model IS the org)
- `StoredFileViewSet` — uses `ModelViewSetMixin` only (per-file permission model)
- `OrganizationImageViewSet` — uses `ModelViewSetMixin` only (images are globally visible)

**Viewsets with completely different patterns:**

- `SignupViewSet` — extends `viewsets.ModelViewSet` directly, no mixins, uses `AllowAny` permission
- `TokenObtainPairView` — extends SimpleJWT's `TokenObtainPairView`
- `PasswordResetRequestView` / `PasswordResetConfirmView` — extend `APIView`

### ViewSet Base Inheritance Chain

```
MyViewSet
  → OrganizationScopedViewSetMixin
      → OrganizationScopedRequestMixin
          → RequestUserMixin              (generics)
  → ModelViewSetMixin
      → OrganizationScopedRequestMixin   (via C3 linearization)
  → viewsets.ModelViewSet
      → GenericViewSet
          → ViewSetMixin
      → CreateModelMixin, ListModelMixin, RetrieveModelMixin,
        UpdateModelMixin, DestroyModelMixin
```

---

## Naming Conventions

### Models

- Use **singular** names: `Organization`, `Member`, `Team`, `TeamMember`.
- All domain models inherit from `apps.generics.models.abstracts.BaseModel`.
- Field names use `snake_case`.
- `ForeignKey`/`OneToOneField` always specify `related_name` explicitly.
- Use `verbose_name` and `verbose_name_plural` in `Meta` classes.

### Files

- One model per file inside `models/`. File name matches the model in singular:
  `member.py`, `organization.py`, `team.py`.
- Serializers mirror the model file name: `member.py`, `organization.py`.
- Permissions, filters, managers, and factories follow the same convention.

### URLs

- URL path segments are **plural** and **hyphenated**: `team-members`, `stored-files`.
- Router basenames use `snake_case`: `team_members`, `stored_files`.
- `app_name` namespace matches the app: `accounts`, `teams`.

### Tests

- Follow the modular test pattern in [`patterns/test-patterns.md`](./patterns/test-patterns.md).
- Test files live in `tests/test_{resource}/`.
- One file per concern: `test_model.py`, `test_serializer.py`, `test_crud.py`,
  `test_permission.py`, `test_filter.py`, `test_choices.py`, `test_integration.py`.
- Test classes: `{Resource}{Category}TestCase`.
- Test methods: `test_{scenario}` (no docstrings).

---

## Code Organization Rules

- Put organization, membership, invitation, file, and auth logic in
  `apps/accounts/`.
- Put team and team membership logic in `apps/teams/`.
- Put reusable cross-app code in `apps/generics/`.
- Avoid duplicating shared helpers in feature apps when a generic helper belongs
  in `apps/generics/`.
- View mixins that depend on domain models (`ModelViewSetMixin`,
  `OrganizationScopedViewSetMixin`, `FilterSetMixin`) live in
  `apps/accounts/mixins/`. Import from there — they will not be migrated to
  `apps/generics/` because `generics` must remain app-agnostic.

### Dependency Rules

- `apps/generics/` must remain app-agnostic (no imports from `accounts` or `teams`).
- `apps/accounts/` and `apps/teams/` can import from `apps/generics/`.
- `apps/teams/` can import from `apps/accounts/` (for Member, Organization).
- `apps/accounts/` must NOT import from `apps/teams/`.

---

## Complexity Guidelines

- Keep functions under **40 lines**. Refactor longer functions into smaller helpers.
- Limit **cyclomatic complexity** to 4 conditional paths per function. Extract
  nested logic into named helpers or use early returns.
- Avoid duplicating logic across models. If two models share the same
  property/method pattern (e.g., permission hierarchies), extract it into a
  mixin in the same app.

---

## New Resource Checklist

When adding a new API resource, follow this checklist:

- [ ] Model (inheriting `BaseModel`)
- [ ] Manager/queryset (extending `BaseManager.from_queryset(BaseQuerySet)`)
- [ ] Choice enums (in `choices.py` if applicable)
- [ ] Serializer (extending `ModelSerializerMixin`)
- [ ] Filter (extending `FilterSetMixin`)
- [ ] Permission (extending `OrganizationScopedPermission` or `BasePermission`)
- [ ] ViewSet (extending `OrganizationScopedViewSetMixin`, `ModelViewSetMixin`,
      and `viewsets.ModelViewSet`)
- [ ] Factory (extending `ModelFactoryMixin` and `DjangoModelFactory`)
- [ ] URL registration in `urls.py` via `DefaultRouter`
- [ ] Schema decoration with `@extend_schema_model_view_set(model=...)`
- [ ] Tests covering CRUD, permissions, auth, and inactive member scenarios
- [ ] Migration (run `make makemigrations` or `make l_makemigrations`)

When adding tests for a new resource, create the following files inside
`apps/{app}/tests/test_{resource}/`:

- [ ] `__init__.py`
- [ ] `test_model.py`
- [ ] `test_serializer.py`
- [ ] `test_crud.py`
- [ ] `test_permission.py`
- [ ] `test_filter.py`
- [ ] `test_choices.py`
- [ ] `test_integration.py`

See [`patterns/test-patterns.md`](./patterns/test-patterns.md) for the detailed conventions.

---

## Related Patterns

For design pattern details, see:

- [`patterns/structural-patterns.md`](./patterns/structural-patterns.md) — Mixin, Abstract Model, Module
- [`patterns/behavioral-patterns.md`](./patterns/behavioral-patterns.md) — Template Method, Strategy, Validation
- [`patterns/creational-patterns.md`](./patterns/creational-patterns.md) — Factory Method, Builder
- [`patterns/architectural-patterns.md`](./patterns/architectural-patterns.md) — Layered, Facade, Test Infrastructure
- [`patterns/test-patterns.md`](./patterns/test-patterns.md) — Modular test structure, coverage matrix
