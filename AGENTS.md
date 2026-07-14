# AGENTS.md

## Purpose

This repository contains **CrewForge**, a Django REST API for managing:

- organizations
- members
- invitations
- teams
- team memberships
- stored files
- organization images
- organization profiles
- authentication and password reset

The project centers on **organization-aware access control**. Beyond JWT auth,
users can set an active organization context through
`/api/accounts/organizations/{id}/login/`, which stores `organization_id` in the
session. Many queries, permissions, and tests depend on that behavior.


## Authentication Flow

User login in this project must be understood as a 3-step process:

1. Authenticate the user with `POST /api/auth/token/`
2. List the organizations available to that authenticated user with
   `GET /api/accounts/organizations/`
3. Select the active organization context with
   `POST /api/accounts/organizations/{id}/login/`

Important: step 1 authenticates the user, but it does not fully establish the
organization context required by several organization-scoped endpoints. Agents
must not assume that obtaining a JWT alone is enough to represent a fully logged
in user in CrewForge.


## Frontend Integration

For a comprehensive guide to consuming the CrewForge API from a frontend
application (Angular, React, etc.), see
[`docs/frontend-integration-guide.md`](./docs/frontend-integration-guide.md).


## Stack And Runtime

- Python `>=3.14`
- Django
- Django REST Framework
- `django-filter`
- `djangorestframework-simplejwt`
- `drf-spectacular` + sidecar assets
- PostgreSQL
- `uv` for dependency and command execution
- Docker / Docker Compose
- Gunicorn
- Ruff for linting and formatting
- pytest + pytest-django + factory-boy for tests

If the local machine does not match the required Python version or Postgres
setup, prefer the Docker workflow.


## Version Policy

- Python version is pinned to `>=3.14`. Agents must **never** change the
  Python version constraint in `pyproject.toml` without explicit instruction.
- Do not upgrade, downgrade, or pin Django or other dependency versions unless
  explicitly asked.


## Environment Notes

- Copy `example.env` to `.env` for local Docker development.
- `SELF_URL` is required for building absolute file download URLs (`StoredFile.file_url`).
- `FRONTEND_URL` is required for generating invitation accept links (`Invitation.get_invitation_link()`).
- The example development setup uses `DJANGO_SETTINGS_MODULE=config.settings.local`.
- Base settings are production-leaning:
  - `DEBUG = False`
  - secure cookies enabled
  - HSTS enabled
  - SSL redirect enabled
- `config.settings.local` explicitly relaxes those settings for development.
- CORS and cookie SameSite are configured cross-origin by default (`SameSite=None`)
  and overridden to `Lax` in local dev to support HTTP. See `CORS_ALLOW_CREDENTIALS`,
  `SESSION_COOKIE_SAMESITE`, and `CSRF_COOKIE_SAMESITE` in `base.py`.
- `run.sh` runs migrations and `collectstatic` before starting the app.
- In production mode the app runs with Gunicorn on port `8000`.
- In local/dev mode the container runs Django `runserver` on port `8000`.
- `GET /api/accounts/session/config/` is a public diagnostic endpoint that
  returns current cookie and CORS settings. Useful for frontend teams to
  verify connectivity before authentication.
- Cookie rules: `SameSite=None` requires `Secure=True` (HTTPS). Local dev
  (HTTP) must use `SameSite=Lax` + `Secure=False` or the browser will
  silently drop the session cookie.


## API And Domain Conventions

- Accounts endpoints live under `/api/accounts/`.
- Team endpoints live under `/api/teams/`.
- Auth endpoints live under `/api/auth/`.
- Root `/` redirects to Swagger UI at `/api/schema/swagger-ui/`.
- Treat login as a 3-step flow:
  - `POST /api/auth/token/`
  - `GET /api/accounts/organizations/`
  - `POST /api/accounts/organizations/{id}/login/`
- Role hierarchy (both org-level and team-level):
  - Owner
  - Admin
  - Manager
  - Member
- `POST /api/accounts/invitations/{id}/send-email/` sends (or resends) an
  invitation email with 60s cooldown; returns 429 if within cooldown, 400 if
  expired/accepted, 200 on success
- Invitations are looked up by PK (`id`), not by `key` (UUID)
- Invitations list is role-scoped cumulatively: managers see MANAGER+MEMBER,
  admins see ADMIN+MANAGER+MEMBER, owners see all roles
- `StoredFile.file_url` provides absolute download URLs using `SELF_URL`

Preserve this domain model when adding or changing behavior. Permission changes
should be treated as high impact and accompanied by tests.


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

- URL path segments are **plural** and **hyphenated**: `team-members`,
  `stored-files`.
- Router basenames use `snake_case`: `team_members`, `stored_files`.
- `app_name` namespace matches the app: `accounts`, `teams`.

### Tests

- Follow the **modular test pattern** documented in
  [`docs/test-patterns.md`](./docs/test-patterns.md).
- Test files live in a dedicated directory per resource:
  `tests/test_{resource}/`.
- One file per concern: `test_model.py`, `test_serializer.py`,
  `test_crud.py`, `test_permission.py`, `test_filter.py`,
  `test_choices.py`, `test_integration.py`.
- Test classes are `{Resource}{Category}TestCase`:
  `OrganizationImageModelTestCase`.
- Test methods are `test_{scenario}` (no docstrings):
  `test_create_duplicate_type_returns_400`.


## Code Organization Rules

- Put organization, membership, invitation, file, and auth logic in
  `apps/accounts/`.
- Put team and team membership logic in `apps/teams/`.
- Put reusable cross-app code in `apps/generics/`.
- Avoid duplicating shared helpers in feature apps when a generic helper belongs
  in `apps/generics/`.

When adding a new API resource, follow this checklist:

- [ ] model (inheriting `BaseModel`)
- [ ] manager/queryset (extending `BaseManager.from_queryset(BaseQuerySet)`)
- [ ] choice enums (in `choices.py` if applicable)
- [ ] serializer (extending `ModelSerializerMixin`)
- [ ] filter (extending `FilterSetMixin`)
- [ ] permission (extending `OrganizationScopedPermission` or `BasePermission`)
- [ ] viewset (extending `OrganizationScopedViewSetMixin`, `ModelViewSetMixin`,
      and `viewsets.ModelViewSet`)
- [ ] factory (extending `ModelFactoryMixin` and `DjangoModelFactory`)
- [ ] URL registration in `urls.py` via `DefaultRouter`
- [ ] schema decoration with `@extend_schema_model_view_set(model=...)`
- [ ] tests covering CRUD, permissions, auth, and inactive member scenarios
- [ ] migration (run `make makemigrations` or `make l_makemigrations`)

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

See [`docs/test-patterns.md`](./docs/test-patterns.md) for the detailed
conventions.


## Design Patterns Documentation

Detailed pattern documentation is available in `docs/`:

- `docs/structural-patterns.md` - Structural patterns (Mixin, Abstract Model,
  Module)
- `docs/behavioral-patterns.md` - Behavioral patterns (Template Method,
  Strategy, Validation)
- `docs/creational-patterns.md` - Creational patterns (Factory Method, Builder)
- `docs/architectural-patterns.md` - Architectural patterns (Layered, Facade,
  Test Infrastructure)
- `docs/test-patterns.md` - Test patterns (modular directory structure, naming,
  coverage matrix, assertions)


## Feature Specifications

Feature-level specifications and implementation plans live in `.specs/`.
Consult this directory before implementing new features to check for existing
specs, test plans, or acceptance criteria.


## Existing Patterns To Reuse

### Viewsets

Prefer existing shared mixins before creating new behavior:

- `apps.accounts.mixins.views.ModelViewSetMixin`
  - adds the `choices` action for value/label endpoints
  - soft-deletes via `inactivate()` when a model has `is_active`
  - provides `label_expression` and `value_expression` for choices
- `apps.accounts.mixins.views.OrganizationScopedViewSetMixin`
  - scopes querysets by the authenticated organization context
  - supports `organization_filter` for FK traversal (e.g.,
    `team__organization_id`)
  - supports `base_filters` dict for additional fixed filters

Standard viewset MRO:

```python
class MyViewSet(
    OrganizationScopedViewSetMixin,
    ModelViewSetMixin,
    viewsets.ModelViewSet,
):
    ...
```

### Serializers

- Extend `ModelSerializerMixin` (from `apps.accounts.mixins.serializers`)
  for all model serializers.
- `ModelSerializerMixin` automatically populates `created_by`, `updated_by`,
  and `organization` from the auth context.
- Default read-only fields: `id`, `is_active`, `created_at`, `updated_at`,
  `created_by`, `updated_by`.
- Use `ValidateRoleSerializerMixin` for any serializer that modifies a `role`
  field. The mixin enforces hierarchical role assignment: setting OWNER/ADMIN
  requires `has_owner_permission`, MANAGER requires `has_admin_permission`,
  MEMBER requires `has_manager_permission`.
- Use `UserTokenSerializerMixin` for serializers that return JWT tokens
  (signup, member creation via invitation).

### Permissions

- Extend `OrganizationScopedPermission` for organization-scoped resources.
- Extend `IsActiveMember` for endpoints that require an authenticated active
  member but not necessarily object-level org scoping.
- `organization_lookup` can be overridden for FK traversal
  (e.g., `'team.organization_id'`).
- `OrganizationAdminObjPermission` (in `apps/accounts/permissions/generics.py`)
  is a reusable base for resources where any active member can read but admin+
  role is required for write. It uses `IsActiveMember` by composition and
  checks `role >= Role.ADMIN` on write. It does **not** override
  `has_permission` — viewsets must add `IsActiveMember` separately in
  `permission_classes`.
- Object-level permissions should always allow SAFE methods (GET, HEAD, OPTIONS)
  before checking write access, unless the resource explicitly requires role
  scoping on reads (e.g., `InvitationPermission` — all actions require
  matching role level).

### Schema

Keep API documentation consistent by reusing:

- `apps.generics.utils.schema.extend_schema_model_view_set`
- `apps.generics.utils.schema.extend_schema_choices_route`

If an endpoint changes request/response behavior, update the schema annotations
and regenerate `schema.yml`.

### Filtering

The default DRF filter backend is `django_filters.rest_framework.DjangoFilterBackend`.
Prefer explicit filter classes in each app instead of ad-hoc query parsing.
Extend `FilterSetMixin` (from `apps.accounts.mixins.filters`) to access auth
context in filters.

### i18n

User-facing strings and schema descriptions commonly use `gettext_lazy`.
Follow that pattern for new API messages and schema text.


## Style And Formatting

Ruff configuration in `pyproject.toml` is the source of truth:

- line length: `88`
- indent width: `4`
- target version: `py314`
- quote style: `single`
- lint rules selected: `E`, `F`, `I`, `B`, `W`

Ruff excludes migrations, caches, virtualenvs, and `__init__.py` files in the
configured paths. Even so, keep those files clean and minimal.


## Testing Guidance

- Test framework: `pytest` / `pytest-django`
- API tests currently use DRF `APITestCase` heavily
- Prefer `factory-boy` factories over manual object creation
- Test files live under `apps/*/tests/`
- Follow the **modular test pattern** documented in
  [`docs/test-patterns.md`](./docs/test-patterns.md) for all new resources

### Test Infrastructure

- `apps.accounts.tests.client.CustomAPIClient` - Custom API client with
  `force_authenticate(member=...)` that authenticates the underlying user and
  also performs organization login.
- `apps.accounts.tests.mixins.APITestCaseMixin` - Provides `new_account()` which
  creates an organization and can auto-login the owner.

Use these helpers whenever the behavior under test depends on
`request.session['organization_id']`.

### Test Coverage Requirements

Target minimum coverage:

| Module | Minimum Target |
|--------|----------------|
| Models | 85% |
| Views/ViewSets | 70% |
| Serializers | 60% |
| Permissions | 50% |
| Utils/Helpers | 100% |
| Overall | 88% |

Every new endpoint or modified behavior should have tests covering:

1. **Happy path**: successful CRUD operations.
2. **Authentication**: unauthenticated requests return 401.
3. **Authorization**: users without proper role/permission get 403.
4. **Inactive members**: inactive members get 403.
5. **Cross-org isolation**: accessing another organization's resources returns
   404 (not 403, because `OrganizationScopedViewSetMixin` filters the
   queryset).
6. **Edge cases**: duplicates, expired invitations, invalid data.

### Factory Pattern

- All factories extend `ModelFactoryMixin` and `DjangoModelFactory`.
- Use `factory.SubFactory` with `SelfAttribute` to propagate shared context
  (e.g., ensuring team and member belong to the same organization).
- Use `Factory.build()` for test data generation without DB persistence.
- Use `Factory.create()` or `Factory.create_batch()` when DB records are
  needed.

### Test Naming

```
test_{action}                    # basic: test_create_invitation
test_{action}_{scenario}         # with context: test_create_member_with_invite_expired
test_not_{condition}_{action}    # negation: test_not_permission_member_update
test_not_authenticated_{action}  # auth: test_not_authenticated_list_members
test_not_active_member_{action}  # inactive: test_not_active_member_retrieve_member
```

### Test Development Rules

- During test development, write **only test code**. Do not implement the
  functionality under test.
- The only exception: if running a test raises an unexpected exception in
  production code (indicating a bug, not a test issue), the agent may fix
  the production code to make the test pass.


## Security Considerations

- Never commit secrets. Use environment variables via `.env`.
- `SECRET_KEY` must be set via `DJANGO_SECRET_KEY` env var. The fallback value
  in `base.py` is a placeholder for development only.
- `ALLOWED_HOSTS` should be restricted in production.
- `CSRF_COOKIE_SECURE` and `SESSION_COOKIE_SECURE` are `True` by default.
  Only `local.py` relaxes these.
- Never log or return passwords, tokens, or secrets in API responses.
- Passwords are always `write_only` in serializers and handled via
  `set_password()`.
- Permission changes are high-impact: always add tests and review carefully.
- Never put real secrets in `example.env`. Use placeholder values only
  (e.g., `SECRET_KEY=change-me-in-production`).


## Performance Guidelines

### Database Queries

- Add `select_related` for `ForeignKey`/`OneToOneField` in viewset querysets
  to avoid N+1 queries.
- Add `prefetch_related` for `ManyToManyField` in viewset querysets.
- Example:
  ```python
  queryset = Member.objects.select_related('user', 'organization').all()
  ```

### Indexes

- Add `db_index=True` or `Meta.indexes` for fields used in frequent lookups,
  filters, or unique constraints (e.g., `slug`, `email`, `key`).
- Composite indexes should be defined in `Meta.indexes` for fields often
  queried together.

### When to Optimize

- Profile before optimizing; do not add indexes or caching speculatively.
- Cache configuration is planned and will be documented in `.specs/` when
  implemented.


## Database Transaction Guidelines

- Use `@transaction.atomic` for operations requiring multi-model consistency.
- For bulk operations, consider `transaction.on_commit()`.
- Always check `connection.atomic_blocks` in sensitive contexts.
- Avoid unnecessary transactions in read-only operations.


## Logging Standards

- Use `logging.getLogger(__name__)` for all loggers.
- Levels:
  - `DEBUG`: Query strings, debug variables
  - `INFO`: CRUD operations, login/logout
  - `WARNING`: Unexpected but non-critical situations
  - `ERROR`: Treated exceptions (send to Sentry)
  - `CRITICAL`: Critical failures (send to Sentry + alert)
- Never log passwords, tokens, or sensitive data.
- In production, integrate with Sentry for error tracking.
- Add `request_id` or `correlation_id` to API request logs for tracing.


## Sentry Integration

When implementing Sentry error tracking, follow these patterns:

- Sentry SDK initialization goes in `config/settings/base.py` with environment-based config
- Use `SENTRY_DSN` environment variable to enable/disable (empty = disabled)
- Create middleware in `apps/generics/middleware/` to add user and organization context
- Set `send_default_pii=False` to avoid capturing sensitive user data
- Use different DSNs for production vs development environments
- See `.specs/sentry_integration_spec.md` for detailed implementation guide


## Error Handling Guidelines

- Never catch bare `Exception`. Catch specific exception types
  (`IOError`, `FileNotFoundError`, `ValueError`, `ObjectDoesNotExist`, etc.).
- Always verify that objects returned by helper functions are not `None` before
  accessing attributes (e.g., `get_member(request)` may return `None`).
- Use Django's built-in exceptions (`Http404`, `PermissionDenied`) for HTTP
  error responses instead of raising generic exceptions.

### Error Response Format

All API errors now use a standardized JSON envelope implemented by
`apps/generics/exceptions.crewforge_exception_handler`:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human readable description",
    "details": {"field": "specific error"}
  }
}
```

| Error code | HTTP status | `details` |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Per-field dict |
| `AUTHENTICATION_ERROR` | 401 | `null` |
| `PERMISSION_DENIED` | 403 | `null` |
| `NOT_FOUND` | 404 | `null` |
| `METHOD_NOT_ALLOWED` | 405 | `null` |
| `NOT_ACCEPTABLE` | 406 | `null` |
| `THROTTLED` | 429 | `null` |
| `INTERNAL_ERROR` | 500 | `null` |

- Never expose stack traces in production (DEBUG=False)
- For permission denied, return 403
- For resources not found, return 404 (not 403) to avoid resource enumeration


## Cache Guidelines

Caching is planned for future implementation. When implemented, follow:

- Add cache only after profiling identifies bottlenecks.
- Use Redis as cache backend (see `.specs/cache_feature_spec.md`).
- Implement cache invalidation on model changes.
- Cache key naming: `crewforge:{app}:{model}:{action}:{identifier}`
- TTL guidelines:
  - Sessions: 15 min
  - List endpoints: 5-15 min
  - Detail endpoints: 5 min
- Never cache sensitive data (passwords, tokens).
- Target cache hit ratio > 80% for hot data.


## Code Complexity Guidelines

- Keep functions under 40 lines. Refactor longer functions into smaller helpers.
- Limit cyclomatic complexity to 4 conditional paths per function. Extract
  nested logic into named helpers or use early returns.
- Avoid duplicating logic across models. If two models share the same
  property/method pattern (e.g., permission hierarchies), extract it into a
  mixin in the same app.


## Required Checks Before Finishing

Run the relevant checks for the change you made:

- `make l_format_code` (ruff check + format)
- `make l_test` (pytest)
- `make l_spectacular` if you changed endpoints, serializers, filters,
  examples, or schema annotations

If models change, create and review migrations as part of the same change.


## Commit Conventions

Follow the conventional commit format documented in
[`.github/git-commit-instructions.md`](./.github/git-commit-instructions.md).
Use the emoji + type prefix pattern:

| Change type | Emoji | Prefix |
|---|---|---|
| New feature | ✨ `:sparkles:` | `feat` |
| Bug fix | 🐛 `:bug:` | `fix` |
| Documentation | 📚 `:books:` | `docs` |
| Tests | 🧪 `:test_tube:` | `test` |
| Refactoring | ♻️ `:recycle:` | `refactor` |
| Chore | 🔧 `:wrench:` | `chore` |
| Cleanup | 🧹 `:broom:` | `cleanup` |
| Removal | 🗑️ `:wastebasket:` | `remove` |

First line should be at most 4 words after the prefix.
Example: `✨ feat: add login page`


## Practical Guardrails For Agents

- Do not replace the organization-context login flow with JWT-only assumptions.
- Do not switch the project to SQLite; configuration and tests are built around
  PostgreSQL.
- Do not bypass existing permission classes when adding new actions.
- Keep Swagger/ReDoc behavior working from `config/urls.py`.
- Keep README-visible behavior and generated schema aligned when the API surface
  changes.
- Do not add comments to code unless explicitly asked.
- Follow the existing MRO order for viewset mixins:
  `OrganizationScopedViewSetMixin` -> `ModelViewSetMixin` ->
  `viewsets.ModelViewSet`.
- When creating models in a new app, always import and extend classes from
  `apps/generics/` (not from `apps/accounts/`) for base abstractions
  (`BaseModel`, `BaseManager`, `BaseQuerySet`).
- View mixins that depend on domain models (`ModelViewSetMixin`,
  `OrganizationScopedViewSetMixin`, `FilterSetMixin`) live in
  `apps/accounts/mixins/`. Import from there — they will not be migrated to
  `apps/generics/` because `generics` must remain app-agnostic.


## Definition Of Done

A change is usually ready when:

- code follows the existing app boundaries
- naming conventions are respected (see Naming Conventions section)
- permissions and organization scoping are preserved
- tests cover the new behavior or regression (happy path, auth, permissions,
  inactive, cross-org)
- Ruff passes (`make l_format_code`)
- tests pass (`make l_test`)
- OpenAPI schema is regenerated when API contracts changed
  (`make l_spectacular`)
- migrations are created and reviewed if models changed
- `docs/frontend-integration-guide.md` is updated when adding new endpoints or changing request/response contracts
