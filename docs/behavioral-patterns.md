# Behavioral Design Patterns

This document describes the behavioral design patterns used in CrewForge.

---

## Table of Contents

- [Template Method Pattern](#template-method-pattern)
- [Strategy Pattern](#strategy-pattern)
- [Validation Chain Pattern](#validation-chain-pattern)

---

## Template Method Pattern

The Template Method pattern defines the skeleton of an algorithm in a base class, letting subclasses override specific steps without changing the algorithm's structure.

### EmailBase

Location: `apps/generics/mails/bases.py`

`EmailBase` defines a fixed sequence for composing and sending HTML emails. Subclasses override attributes and hooks to customize content.

**Template structure:**

1. `get_context_data()` assembles the context dict from getter methods
2. `get_message()` renders the template, builds `EmailMultiAlternatives`, and attaches files
3. `send()` dispatches the email

**Subclass customization points:**

| Override | Purpose |
|----------|---------|
| `template_name` | Django template path |
| `subject` | Email subject line |
| `recipient_list` | Default recipients |
| `preheader` | Preview text for email clients |
| `theme_color` | Brand color for email styling (default `'#002180'`) |
| `title` | Main heading |
| `content` | Body content |
| `logo` | URL or path to logo image |
| `cta` | `CTAEmail` button instance |
| `footer_text` | Footer text content |
| `system_company_address` | Company address in footer |
| `unsubscribe_url` | Unsubscribe link URL |
| `file_path` | Path to attachment file |
| `file_name` | Attachment display name |
| `file_mimetype` | Attachment MIME type |
| `from_email` | Sender email (default `settings.FROM_MAIL`) |
| `language` | Email language (default `settings.LANGUAGE_CODE`) |
| `system_title` | System title (default `settings.SYSTEM_TITLE`) |
| `get_preview_kwargs()` | Provide test data for preview mode |

**Usage example:**

```python
from apps.generics.mails.bases import CTAEmail, EmailBase


class PasswordResetRequestEmail(EmailBase):
    template_name = 'accounts/emails/base.html'

    subject = _('Password Reset')
    preheader = _('Use the link below to reset your password.')
    title = _('Password Reset Request')
    content = _(
        'We received a request to reset your password. '
        'Click the button below to set a new password.'
    )

    def __init__(self, *, reset_url: str, **kwargs):
        super().__init__(**kwargs)
        self.cta = CTAEmail(url=reset_url, text=_('Reset Password'))
```

**Preview support:**

Each email class can generate a Django view for preview in development:

```python
# In urls.py (local/test only)
path(
    route='email-preview/auth/password/reset/',
    view=PasswordResetRequestEmail.as_view(),
    name='password_reset_email_preview',
)
```

---

### BaseModel Soft-Delete Methods

Location: `apps/generics/models/abstracts.py`

`BaseModel` provides `activate()` and `inactivate()` as a template for soft-delete operations. Subclasses inherit the behavior without overriding.

```python
def activate(self):
    self.is_active = True
    self.save()

def inactivate(self):
    self.is_active = False
    self.save()
```

These methods are called by `ModelViewSetMixin.perform_destroy()`, which serves as the template method for delete operations in viewsets:

```python
def perform_destroy(self, instance):
    if hasattr(instance, 'is_active'):
        instance.inactivate()
    else:
        super().perform_destroy(instance)
```

---

## Strategy Pattern

The Strategy pattern encapsulates interchangeable algorithms behind a common interface. CrewForge uses this for permission checking.

### Permission Hierarchy

Location: `apps/accounts/permissions/generics.py`

Two base permission classes form a strategy chain:

```
IsAuthenticated (DRF)
  └── IsActiveMember
        └── OrganizationScopedPermission
              ├── MemberPermission
              ├── InvitationPermission
              ├── TeamPermission
              └── TeamMemberPermission

BasePermission (DRF)
  ├── StoredFilePermission          # Independent access-level strategy
  │     └── OrganizationImagePermission  # Delegates to StoredFilePermission
  └── OrganizationPermission        # Owner-only, not org-scoped (it IS the org)
```

### IsActiveMember

Requires an authenticated user with an active member record in the current organization session.

```python
class IsActiveMember(IsAuthenticated):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and (member := get_member(request))
            and member.is_active
        )

    def has_object_permission(self, request, view, obj):
        return (
            super().has_object_permission(request, view, obj)
            and (member := get_member(request))
            and member.is_active
        )
```

### OrganizationScopedPermission

Extends `IsActiveMember` with organization-level object scoping.

```python
class OrganizationScopedPermission(IsActiveMember):
    organization_lookup = 'organization_id'

    @classmethod
    def get_request_member(cls, request):
        return get_member(request)

    @classmethod
    def get_session_organization_id(cls, request):
        return get_organization_id(request)

    @classmethod
    def has_organization_scope(cls, request, obj) -> bool:
        organization_id = cls.get_session_organization_id(request)
        return is_same_organization_scope(
            obj=obj,
            organization_id=organization_id,
            lookup=cls.organization_lookup,
        )

    def has_object_permission(self, request, view, obj):
        return super().has_object_permission(
            request, view, obj
        ) and self.has_organization_scope(request, obj)
```

**Key attribute:** `organization_lookup` can be overridden for FK traversal:

```python
# For nested resources like TeamMember -> Team -> Organization
class TeamMemberPermission(OrganizationScopedPermission):
    organization_lookup = 'team.organization_id'
```

### Concrete Strategies

Each resource defines its own permission strategy by extending `OrganizationScopedPermission` or `BasePermission`:

**MemberPermission** (`apps/accounts/permissions/member.py`):
- Allows `create_with_invite` without prior auth
- SAFE methods always allowed for active members
- Admins can delete members
- Owners can modify any member; admins can modify non-owners
- Active members can update their own record (`request.user.id == obj.user_id`)

**InvitationPermission** (`apps/accounts/permissions/invitation.py`):
- Extends `OrganizationScopedPermission`
- Write access requires `has_admin_permission` at the permission level
- Object-level checks match invitation role against auth member's role:
  - OWNER invitations require owner permission
  - ADMIN invitations require admin permission
  - MANAGER invitations require manager permission
  - MEMBER invitations require member permission

**TeamPermission** (`apps/teams/permissions/team.py`):
- SAFE methods allowed for all active members
- Write operations require `has_manager_permission` or team-level admin role

**TeamMemberPermission** (`apps/teams/permissions/team_member.py`):
- Extends `OrganizationScopedPermission` with `organization_lookup = 'team.organization_id'`
- SAFE methods allowed for all active members
- Write operations require `has_manager_permission` or team-level admin role

**OrganizationPermission** (`apps/accounts/permissions/organization.py`):
- Extends `BasePermission` directly (not org-scoped, since it IS the org)
- Owner-only modifications, with SAFE methods and login action as exceptions
- Login action additionally checks that the user is an active member (`is_member`)

**StoredFilePermission** (`apps/accounts/permissions/files.py`):
- Extends `BasePermission` directly (uses its own access-level strategy)
- Uses `StoredFileAccess` enum for granular permission levels:
  - `PUBLIC` — anyone (including anonymous)
  - `OWNER` — file owner only (by user ID)
  - `MEMBERS_ORGANIZATION` — any active member in the org
  - `MANAGERS_ORGANIZATION` — manager role and above
  - `ADMINS_ORGANIZATION` — admin role and above
  - `OWNERS_ORGANIZATION` — owner role only
- Separate `viewing_permission` and `updating_permission` fields
- Superuser bypasses all checks
- Cross-org returns 404 (not 403)

**OrganizationImagePermission** (`apps/accounts/permissions/organization_image.py`):
- Extends `BasePermission` directly
- Delegates `has_permission` to `StoredFilePermission`
- Object-level access combines `StoredFilePermission` with admin-level write gate
- SAFE methods always allowed for reading; writes require admin role in the same org

---

## Validation Chain Pattern

Serializer mixins form a validation chain that runs during `is_valid()`, adding domain-specific checks.

### ValidateRoleSerializerMixin

Location: `apps/accounts/serializers/mixins.py`

Validates role field changes with hierarchical permission checks:

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

**Validation rules:**
1. Users cannot change their own role
2. Only owners can assign the `OWNER` role
3. Only owners or admins can assign the `ADMIN` role

**Used by:** Serializers that modify the `role` field on `Member` instances.

### UserTokenSerializerMixin

Location: `apps/accounts/serializers/mixins.py`

Injects JWT token generation into serializer output via metaclass:

```python
class UserTokenSerializerMetaclass(SerializerMetaclass):
    def __new__(cls, name, bases, attrs):
        attrs['refresh'] = serializers.SerializerMethodField()
        attrs['access'] = serializers.SerializerMethodField()
        return super().__new__(cls, name, bases, attrs)


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
        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, user)


class UserTokenSerializerMixin(UserTokenMixin, metaclass=UserTokenSerializerMetaclass):
    pass
```

**Used by:**
- `SignupSerializer` — returns tokens on registration
- `MemberWithInviteCreateSerializer` — returns tokens when creating a member via invitation

---

## Related Patterns

- [Structural Patterns](./structural-patterns.md) (Mixin, Abstract Model, Module)
- [Creational Patterns](./creational-patterns.md) (Factory Method, Builder)
- [Architectural Patterns](./architectural-patterns.md) (Layered, Facade, Test Infrastructure)
- [Test Patterns](./test-patterns.md) (Modular test structure, coverage matrix)
