# Architectural Patterns

This document describes the architectural patterns used in CrewForge.

---

## Table of Contents

- [Layered Architecture](#layered-architecture)
- [Facade Pattern](#facade-pattern)
- [Test Infrastructure](#test-infrastructure)

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

### Data Flow

A typical request flows through:

1. **URL Router** → dispatches to the correct ViewSet
2. **ViewSet** → applies `get_queryset()` with organization scoping
3. **Permission** → checks authentication, membership, and role
4. **Filter** → applies query parameter filters
5. **Serializer** → validates input or serializes output
6. **Model/Manager** → executes database operations

All layers depend on the **generics foundation** (`BaseModel`, `BaseManager`,
`BaseQuerySet`, `RequestUserMixin`, `AuthUserFieldMixin`, schema utils, etc.).

### ViewSet Composition

#### Standard MRO

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
    OrganizationScopedViewSetMixin,    # 1st: scope by org
    ModelViewSetMixin,                  # 2nd: soft-delete + choices
    viewsets.ModelViewSet,              # 3rd: DRF base
):
    serializer_class = MySerializer
    queryset = MyModel.objects.all()
    permission_classes = [MyPermission]
    filterset_class = MyFilter
    label_expression = 'name'
```

Additional attributes commonly used:

| Attribute | Purpose | Example |
|-----------|---------|---------|
| `filter_backends` | DRF filter backends | `[backends.DjangoFilterBackend]` (set in all viewsets) |
| `http_method_names` | Restrict allowed verbs | `['get', 'post']` |
| `base_filters` | Additional fixed filters | `{'is_active': True}` |
| `organization_filter` | FK traversal override | `'team__organization_id'` |
| `lookup_field` | Non-default PK field | `'uuid'` for StoredFile, `'key'` for Invitation |
| `parser_classes` | Request parsing | `[MultiPartParser, FormParser]` for file uploads |

#### MRO Variations

Not all viewsets follow the standard pattern. The following variations exist:

**Viewsets without `OrganizationScopedViewSetMixin`:**

These resources are not scoped to a single organization for list operations:

- `OrganizationViewSet` — uses `ModelViewSetMixin` only (the model IS the org)
- `StoredFileViewSet` — uses `ModelViewSetMixin` only (per-file permission model)
- `OrganizationImageViewSet` — uses `ModelViewSetMixin` only (images are globally visible)

**Viewsets with completely different patterns:**

- `SignupViewSet` — extends `viewsets.ModelViewSet` directly, no mixins, uses
  `AllowAny` permission, only allows `POST`, uses `@extend_schema_view` directly
- `TokenObtainPairView` — extends SimpleJWT's `TokenObtainPairView` (not a ModelViewSet)
- `PasswordResetRequestView` / `PasswordResetConfirmView` — extend `APIView`

#### ViewSet Base Inheritance Chain

The full resolved MRO for a compliant viewset at runtime is:

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

## Facade Pattern

Facade patterns simplify complex operations by providing a unified interface over multiple subsystems.

### Schema Facade

Location: `apps/generics/utils/schema.py`

`extend_schema_model_view_set` provides a single decorator that configures all standard CRUD schema annotations for a ViewSet:

```python
def extend_schema_model_view_set(
    *,
    model: type[BaseModel],
    **kwargs,
):
    kwargs.setdefault('retrieve', extend_schema_retrieve(model=model))
    kwargs.setdefault('list', extend_schema_list(model=model))
    kwargs.setdefault('create', extend_schema_create(model=model))
    kwargs.setdefault('destroy', extend_schema_destroy(model=model))
    kwargs.setdefault('update', extend_schema_update(model=model))
    kwargs.setdefault('partial_update', extend_schema_partial_update(model=model))
    kwargs.setdefault('options', extend_schema_options(model=model))
    kwargs.setdefault('choices', extend_schema_choices_route(model=model))
    return extend_schema_view(**kwargs)
```

**Usage:**

```python
@extend_schema_model_view_set(model=Team)
class TeamViewSet(OrganizationScopedViewSetMixin, ModelViewSetMixin, viewsets.ModelViewSet):
    ...
```

This replaces 8 individual `@extend_schema` decorators with a single annotation.
Viewsets that add custom actions (e.g., `login`, `create_with_invite`,
`update_role`, `file`) override the relevant operation with a more specific
`@extend_schema` decorator on top of the facade.

### Request Helper Facade

Location: `apps/accounts/utils/requests.py`

Utility functions that encapsulate the multi-step process of extracting organization context from requests:

```python
def get_organization_id(request: Request) -> int | None:
    """Get the organization ID from the request."""
    if not request or not request.user.is_authenticated:
        return None
    return request.session.get('organization_id')


def get_organization(request: Request) -> Organization | None:
    """Get the organization from the request."""
    if not (organization_id := get_organization_id(request)):
        return None
    return request.user.organizations.filter(is_active=True).get_or_none(
        id=organization_id
    )


def get_member(request: Request) -> Member | None:
    """Get the member from the request."""
    if not request:
        return None
    user = request.user
    if not user.is_authenticated:
        return None
    if not (organization_id := request.session.get('organization_id')):
        return None
    return user.members.filter(is_active=True).get_or_none(
        organization_id=organization_id
    )


def is_same_organization_scope(
    obj,
    organization_id: int | None,
    lookup: str = 'organization_id',
    separator: str = '.',
) -> bool:
    """Check whether an object belongs to the given organization scope."""
    if not organization_id:
        return False
    current = obj
    for attr in lookup.split(separator):
        current = getattr(current, attr, None)
        if current is None:
            return False
    return current == organization_id
```

**Key features:**
- `get_organization_id()` — reads from session
- `get_organization()` — resolves the active org with `get_or_none()`
- `get_member()` — resolves the active member
- `is_same_organization_scope()` — supports dotted FK traversal via `separator`

### Serializer Context Facade

Location: `apps/generics/utils/serializers.py`

Encapsulates the logic for extracting an authenticated user from serializer context:

```python
def get_user_of_context(context: dict) -> User | None:
    request = context.get('request')
    if not request:
        return None
    elif not (user := request.user):
        return None
    elif not user.is_authenticated:
        return None
    if not user.is_active:
        return None
    return user
```

### CORS and Cookie Configuration

The organization context relies on the session cookie being sent from the SPA
to the API. This requires explicit CORS and SameSite configuration depending
on the deployment topology.

**Production defaults** (`config/settings/base.py`):

```python
CORS_ALLOW_CREDENTIALS = True               # allow withCredentials cookies
SESSION_COOKIE_SAMESITE = 'None'            # cross-origin SPA support
CSRF_COOKIE_SAMESITE = 'None'               # cross-origin CSRF support
SESSION_COOKIE_SECURE = True                # required when SameSite=None
```

**Local development** (`config/settings/local.py`) overrides SameSite to `Lax`
and Secure to `False` because modern browsers reject `SameSite=None` without
`Secure=True` on HTTP.

| Scenario | `SameSite` | Extra config |
|---|---|---|
| Same domain (`app.com/api`) | `Lax` or `None` | none |
| Subdomains (`app.com` + `api.app.com`) | `Lax` | `SESSION_COOKIE_DOMAIN=.app.com` (optional) |
| Different domains (`app.com` + `api.com`) | `None` | `CSRF_TRUSTED_ORIGINS=https://app.com` |

All three values are configurable via environment variables:

- `CORS_ALLOWED_ORIGINS` — comma-separated list of allowed origins
- `SESSION_COOKIE_SAMESITE` — `'Lax'` or `'None'`
- `CSRF_COOKIE_SAMESITE` — `'Lax'` or `'None'`
- `SESSION_COOKIE_DOMAIN` — shared cookie domain for subdomains
- `CSRF_TRUSTED_ORIGINS` — comma-separated list for CSRF protection

---

## Test Infrastructure

CrewForge provides shared test infrastructure for consistent API testing.

### CustomAPIClient

Location: `apps/accounts/tests/client.py`

Extends DRF's `APIClient` with organization-aware authentication:

```python
class CustomAPIClient(APIClient):
    def force_authenticate(
        self,
        user=None,
        token=None,
        member: MemberFactory | Member | None = None,
        organization_auth: bool = True,
    ):
        if not member:
            super(CustomAPIClient, self).force_authenticate(user=user, token=token)
            return

        super(CustomAPIClient, self).force_authenticate(user=member.user, token=token)
        if organization_auth:
            self.post(
                path=reverse(
                    viewname='accounts:organizations-login',
                    args=[member.organization_id],
                ),
                format='json',
            )
```

**Key behavior:** When authenticating with a `member`, it automatically performs the organization login step (step 3 of the auth flow), setting `organization_id` in the session.

### APITestCaseMixin

Location: `apps/accounts/tests/mixins.py`

Provides `new_account()` helper for creating organizations with authenticated owners:

```python
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
```

**Parameters:**
- `login=True` — authenticate the user
- `organization_login=True` — also perform organization login (sets session context)

### Usage in Tests

```python
class TestMembersAPITestCase(APITestCaseMixin, APITestCase):
    def test_list_members(self):
        org = self.new_account()
        response = self.client.get('/api/accounts/members/')
        self.assertEqual(response.status_code, 200)

    def test_not_authenticated_list_members(self):
        response = self.client.get('/api/accounts/members/')
        self.assertEqual(response.status_code, 401)
```

> For detailed test structure, naming, coverage matrix, and conventions, see
> [Test Patterns](./test-patterns.md).

---

## Additional Architectural Patterns

### URL Routing Organization

`config/urls.py` groups URL patterns into categories:

```python
django_urlpatterns = [...]       # Admin
third_party_urlpatterns = [...]  # Swagger, ReDoc, Schema, Root redirect
local_urlpatterns = [...]        # App routers
```

`apps/accounts/urls.py` further splits into authentication and account routes:

```python
authentication_urlpatterns = [...]  # Token obtain/refresh/verify, password reset
accounts_urlpatterns = [...]        # Organizations, members, invitations, files, images
```

### Serializer Composition

Model serializers compose behaviors through mixin inheritance:

```python
class MySerializer(
    ModelSerializerMixin,              # Auto-populates created_by, updated_by, organization
    serializers.ModelSerializer,
):
    ...
```

Additional mixins for specific needs:

- `ValidateRoleSerializerMixin` — validates role field changes with hierarchy checks
- `UserTokenSerializerMixin` — injects JWT `refresh`/`access` fields via metaclass
- `ChoiceSerializer` (`apps/generics/serializers/choices.py`) — value/label output format

### App-Specific Settings

`apps/accounts/settings.py` defines a `api_settings` object (following SimpleJWT's
pattern) that exposes app-level configuration:

```python
from apps.accounts.settings import api_settings
api_settings.UPDATE_LAST_LOGIN
```

### Custom Serializer Selection

Some viewsets use `get_serializer_class()` instead of a static `serializer_class`
attribute, returning different serializers based on the current action:

- `MemberViewSet` — different serializers for create, update, and update_role
- `StoredFileViewSet` — different serializers for create vs. update
- `TeamMemberViewSet` — different serializers for create vs. update

### Email Subsystem

A complete email composition and preview subsystem lives in `apps/generics/mails/bases.py`:

- `EmailBase` — template method for building and sending HTML emails
- `CTAEmail` — builder for call-to-action buttons
- `EmailView` — Django `TemplateView` for previewing emails in development
- `as_view()` classmethod — converts any `EmailBase` subclass into a Django view

Concrete email classes live in `apps/accounts/emails.py`.

---

## Related Patterns

- [Structural Patterns](./structural-patterns.md) (Mixin, Abstract Model, Module)
- [Behavioral Patterns](./behavioral-patterns.md) (Template Method, Strategy, Validation)
- [Creational Patterns](./creational-patterns.md) (Factory Method, Builder)
- [Test Patterns](./test-patterns.md) (Modular test structure, coverage matrix)
