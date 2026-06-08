# Structural Design Patterns

This document describes the structural design patterns used in CrewForge.

---

## Table of Contents

- [Mixin Pattern](#mixin-pattern)
- [Abstract Model Pattern](#abstract-model-pattern)
- [Module Pattern](#module-pattern)

---

## Mixin Pattern

Mixins are used extensively to compose reusable behavior across multiple classes without inheritance hierarchies.

> **Note**: Mixins that depend on domain models (like `Member`, `Organization`) live in `apps/accounts/mixins/`. Generic, app-agnostic mixins live in `apps/generics/mixins/`.

---

### RequestUserMixin

Location: `apps/generics/mixins/mixins.py`

Provides cached property for accessing authenticated user.

```python
class RequestUserMixin:
    @cached_property
    def auth_user(self) -> User | None:
        if (user := self.request.user) and user.is_authenticated:
            return user
        return None
```

**Used by:**
- `OrganizationScopedRequestMixin` (accounts)

---

### OrganizationScopedRequestMixin

Location: `apps/accounts/mixins/requests.py`

Provides cached properties for accessing authenticated user, member, and organization context.

```python
class OrganizationScopedRequestMixin(RequestUserMixin):
    @cached_property
    def auth_member(self) -> Member | None:
        return get_member(self.request)

    @cached_property
    def auth_organization(self) -> Organization | None:
        return get_organization(self.request)

    @cached_property
    def auth_organization_id(self) -> int | None:
        return get_organization_id(self.request)
```

**Used by:**
- `ModelViewSetMixin` (accounts)
- `OrganizationScopedViewSetMixin` (accounts)
- `FilterSetMixin` (accounts)

---

### ModelViewSetMixin

Location: `apps/accounts/mixins/views.py`

Adds common functionality to DRF ModelViewSets including soft-delete support and a `choices` action endpoint.

```python
class ModelViewSetMixin(OrganizationScopedRequestMixin):
    def perform_destroy(self, instance):
        if hasattr(instance, 'is_active'):
            instance.inactivate()
        else:
            super().perform_destroy(instance)

    def get_label_expression(self) -> str | Combinable:
        if label_expression := getattr(self, 'label_expression', None):
            return label_expression
        raise NotImplementedError('Subclasses must implement this method.')

    def get_value_expression(self) -> str | Combinable:
        if value_expression := getattr(self, 'value_expression', None):
            return value_expression
        elif self.lookup_field:
            return self.lookup_field
        return 'pk'

    @action(detail=False, methods=['get'], url_path='choices')
    def choices(self, request, *args, **kwargs):
        """List items for choices (value/label format)."""
        queryset = self.filter_queryset(self.get_queryset())
        label = self.get_label_expression()
        value = self.get_value_expression()
        choices_queryset = queryset.annotate(
            _choice_label=F(label) if isinstance(label, str) else label,
            _choice_value=F(value) if isinstance(value, str) else value,
        ).values('_choice_value', '_choice_label')
        # Returns paginated {value, label} pairs
        ...
```

**Features:**
- Soft-delete via `inactivate()` when model has `is_active` field
- `choices` action returns data suitable for dropdown selects
- `label_expression` and `value_expression` for customizing choice output

---

### OrganizationScopedViewSetMixin

Location: `apps/accounts/mixins/views.py`

Filters querysets by the authenticated organization context.

```python
class OrganizationScopedViewSetMixin(OrganizationScopedRequestMixin):
    organization_filter = 'organization_id'
    base_filters = {}

    def get_base_queryset_filters(self) -> dict:
        return dict(self.base_filters)

    def get_organization_filter_kwargs(self) -> dict:
        return {self.organization_filter: self.auth_organization_id}

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                **self.get_organization_filter_kwargs(),
                **self.get_base_queryset_filters(),
            )
        )
```

**Usage example:**

```python
@extend_schema_model_view_set(model=Team)
class TeamViewSet(
    OrganizationScopedViewSetMixin, ModelViewSetMixin, viewsets.ModelViewSet
):
    serializer_class = TeamSerializer
    queryset = Team.objects.all()
    permission_classes = [TeamPermission]
    filterset_class = TeamFilter
    label_expression = 'name'
```

---

### ModelSerializerMixin

Location: `apps/accounts/mixins/serializers.py`

Automatically injects `created_by`, `updated_by`, and `organization` into validated data.

```python
class ModelSerializerMixin(OrganizationScopedFieldMixin):
    serializer_related_field = PrimaryKeyRelatedField
    _default_read_only_fields = [
        'id', 'is_active', 'created_at', 'updated_at',
        'created_by', 'updated_by',
    ]

    @property
    def validated_data(self):
        data = dict()
        concrete_fields = [f.attname for f in self.Meta.model._meta.concrete_fields]
        if 'created_by_id' in concrete_fields and not self.instance:
            data.update({'created_by': self.auth_user})
        if 'updated_by_id' in concrete_fields:
            data.update({'updated_by': self.auth_user})
        if 'organization_id' in concrete_fields and not self.instance:
            data.update({'organization': self.auth_organization})
        data.update(super().validated_data)
        return data
```

---

### ValidateRoleSerializerMixin

Location: `apps/accounts/serializers/mixins.py`

Validates role field changes, preventing users from assigning roles above their own permission level.

```python
class ValidateRoleSerializerMixin:
    def validate_role(self, value):
        if self.instance == self.auth_member:
            raise serializers.ValidationError(
                _('Not allowed to change your own role.')
            )
        if (
            value == MemberRoleChoices.OWNER
            and not self.auth_member.has_owner_permission
        ) or (
            value == MemberRoleChoices.ADMIN
            and not self.auth_member.has_admin_permission
        ):
            raise serializers.ValidationError(
                _('Not allowed to set the %(role)s role.') % {'role': value}
            )
        return value
```

**Used by:**
- Member serializers that modify the `role` field

---

### UserTokenSerializerMixin

Location: `apps/accounts/serializers/mixins.py`

Metaclass-based mixin that auto-injects `refresh` and `access` JWT token fields into serializers.

```python
class UserTokenMixin:
    username_field = get_user_model().USERNAME_FIELD

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._refresh_token = None
        self._access_token = None

    def get_refresh(self, obj) -> str | None:
        return self._refresh_token

    def get_access(self, obj) -> str | None:
        return self._access_token

    def set_tokens_for_user(self, user):
        refresh = RefreshToken.for_user(user)
        self._refresh_token = str(refresh)
        self._access_token = str(refresh.access_token)


class UserTokenSerializerMixin(UserTokenMixin, metaclass=UserTokenSerializerMetaclass):
    pass
```

**Used by:**
- `SignupSerializer`
- `MemberWithInviteCreateSerializer` (member creation via invitation)

---

### FilterSetMixin

Location: `apps/accounts/mixins/filters.py`

Base mixin for django-filter FilterSet classes, providing access to user context.

```python
class FilterSetMixin(OrganizationScopedRequestMixin):
    """Mixin for filtersets to add user, member, and organization properties."""
```

---

### OrganizationScopedFieldMixin

Location: `apps/accounts/mixins/fields.py`

Provides authentication context to serializer fields.

```python
class OrganizationScopedFieldMixin(AuthUserFieldMixin):
    @cached_property
    def auth_member(self) -> Member | None:
        return get_member(self.context.get('request'))

    @cached_property
    def auth_organization(self) -> Organization | None:
        return get_organization(self.context.get('request'))

    @cached_property
    def auth_organization_id(self) -> int | None:
        return get_organization_id(self.context.get('request'))
```

---

### AuthUserFieldMixin

Location: `apps/generics/fields/fields.py`

Provides authentication user context to serializer fields.

```python
class AuthUserFieldMixin:
    @cached_property
    def auth_user(self) -> User | None:
        return get_user_of_context(self.context)
```

---

### PrimaryKeyActiveRelatedFieldMixin

Location: `apps/generics/fields/relations.py`

Filters related field querysets to only include active records.

```python
class PrimaryKeyActiveRelatedFieldMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        model = queryset.model
        filters = {'is_active': True} if hasattr(model, 'is_active') else {}
        return queryset.filter(**filters)
```

---

### PrimaryKeyOrganizationRelatedFieldMixin

Location: `apps/accounts/mixins/fields.py`

Filters related field querysets by the authenticated organization context.

```python
class PrimaryKeyOrganizationRelatedFieldMixin(OrganizationScopedFieldMixin):
    def get_queryset(self):
        queryset = super().get_queryset()
        model = queryset.model
        if hasattr(model, 'organization_id'):
            filters = {'organization_id': self.auth_organization_id}
        else:
            filters = {}
        return queryset.filter(**filters)
```

**Combined usage:**

`PrimaryKeyRelatedField` combines both mixins with DRF's `PrimaryKeyRelatedField`:

```python
class PrimaryKeyRelatedField(
    PrimaryKeyActiveRelatedFieldMixin,
    PrimaryKeyOrganizationRelatedFieldMixin,
    relations.PrimaryKeyRelatedField,
):
    """Filters queryset by is_active and organization_id."""
```

---

## Abstract Model Pattern

All domain models inherit from `BaseModel`, which provides common fields and behaviors.

### BaseModel

Location: `apps/generics/models/abstracts.py`

```python
class BaseModel(models.Model):
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='+',
        null=True, blank=True,
    )
    updated_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='+',
        null=True, blank=True,
    )

    objects = BaseManager.from_queryset(BaseQuerySet)

    class Meta:
        abstract = True

    def activate(self):
        self.is_active = True
        self.save()

    def inactivate(self):
        self.is_active = False
        self.save()

    @classmethod
    def schema_tags(cls):
        return [cls._meta.verbose_name_plural.capitalize()]
```

**Benefits:**
- Soft-delete support via `is_active` field
- Audit fields (`created_at`, `updated_at`, `created_by`, `updated_by`)
- Custom manager with common query methods
- Schema documentation helper method

**Usage example:**

```python
class Organization(BaseModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    owner = models.ForeignKey('accounts.Member', ...)

    objects = OrganizationManager()

    class Meta:
        ordering = ['-id']
```

### BaseManager and BaseQuerySet

Location: `apps/generics/managers/querysets.py`

Custom querysets and managers providing common filtering and bulk operations.

```python
class BaseQuerySet(models.QuerySet):
    def filter_actives(self):
        return self.filter(is_active=True)

    def filter_inactives(self):
        return self.filter(is_active=False)

    def get_or_none(self, **kwargs):
        try:
            return self.get(**kwargs)
        except self.model.DoesNotExist:
            return None


class BaseManager(manager.BaseManager.from_queryset(BaseQuerySet)):
    def deactivate(self):
        return self.filter_actives().update(is_active=False)

    def activate(self):
        return self.filter_inactives().update(is_active=True)
```

**Features:**
- `filter_actives()` / `filter_inactives()` — convenience filters for soft-delete
- `get_or_none()` — returns `None` instead of raising `DoesNotExist`
- `activate()` / `deactivate()` — bulk operations on active status

---

## Module Pattern

CrewForge follows a modular architecture with clear separation by domain.

### Directory Structure

```
apps/
├── accounts/                 # Organization, Member, Invitation, User, File management
│   ├── models/              # Domain models (one file per model)
│   ├── serializers/         # DRF serializers
│   ├── views/               # API views/viewsets
│   ├── permissions/         # Permission classes
│   ├── filters/             # django-filter FilterSets
│   ├── managers/            # Custom managers/querysets
│   ├── factories/           # Test factories (factory-boy)
│   ├── mixins/              # View/serializer/filter mixins
│   ├── tests/               # Test suite
│   ├── forms/               # Django admin forms
│   ├── management/          # Management commands
│   ├── templates/           # Email templates
│   ├── migrations/          # Database migrations
│   ├── choices.py           # Choice enums
│   ├── emails.py            # Email classes
│   ├── settings.py          # App-specific settings
│   ├── admin.py             # Django admin configuration
│   ├── apps.py              # App configuration
│   ├── urls.py              # URL routing
│   └── utils/               # Request helpers
├── teams/                    # Team and TeamMember management
│   ├── models/
│   ├── serializers/
│   ├── views/
│   ├── permissions/
│   ├── filters/
│   ├── managers/
│   ├── factories/
│   ├── tests/
│   ├── migrations/
│   ├── choices.py
│   ├── admin.py
│   ├── apps.py
│   └── urls.py
├── generics/                 # Shared cross-domain code
│   ├── models/              # Abstract base models
│   ├── serializers/         # Base serializers
│   ├── fields/              # Custom field mixins
│   ├── mixins/              # Generic mixins (app-agnostic)
│   ├── managers/            # Base managers/querysets
│   ├── factories/           # Factory mixins
│   ├── tests/               # Test suite
│   ├── migrations/          # Database migrations
│   ├── utils/               # Utility functions
│   └── mails/               # Email base classes
```

### Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `accounts` | Organizations, members, invitations, users, files, authentication |
| `teams` | Teams and team memberships |
| `generics` | Reusable base classes, mixins, utilities (app-agnostic) |
| `generics/mails/` | Base classes for HTML email composition and sending |
| `generics/serializers/` | Generic serializers (e.g., `ChoiceSerializer`) |
| `generics/managers/` | `BaseManager` and `BaseQuerySet` |

### App Configuration

Location: `config/settings/base.py`

```python
LOCAL_APPS = [
    'apps.accounts',
    'apps.teams',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
```

---

## Related Patterns

For behavioral, creational, and architectural patterns, see:
- [Behavioral Patterns](./behavioral-patterns.md) (Template Method, Strategy, Validation)
- [Creational Patterns](./creational-patterns.md) (Factory Method, Builder)
- [Architectural Patterns](./architectural-patterns.md) (Layered, Facade, Test Infrastructure)
