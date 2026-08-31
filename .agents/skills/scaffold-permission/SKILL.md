---
name: scaffold-permission
description: >
  Use to generate a permission class for a new Django resource. Follows the
  OrganizationScopedPermission pattern with role-based checks. Called by
  scaffold-resource or standalone for permission-only generation.
metadata:
  author: crewforge
  version: "1.0"
  risk: safe
  type: model-invoked
---

# Scaffold Permission — Permission Class Generator

You will act as a **Security Engineer** specialized in Django REST Framework permission classes.

Your responsibility is to generate a permission class that follows the CrewForge Strategy Chain pattern: `IsAuthenticated` → `IsActiveMember` → `OrganizationScopedPermission` → `{Resource}Permission`.

---

## Prerequisite: Contextualization

Before generating, read:

1. `apps/accounts/permissions/generics.py` — base permission classes
2. `apps/accounts/permissions/` — existing permission patterns
3. `AGENTS.md` — Non-Negotiable Rules about permissions
4. `docs/patterns/behavioral-patterns.md` — Strategy pattern

---

## Workflow

### Phase 1 — Quick Mode (3 questions)

Ask the user:

```
Permission Configuration (Quick):

1. Resource name: [ex: Project]
2. Read: [all authenticated / specific roles]
3. Write: [minimum role: owner/admin/manager/member]
```

Wait for answers. Then ask:

### Phase 1.5 — Detailed Mode (Optional — 4 questions)

Do you want full control over permission configuration? [yes/no]

If yes:

```
Permission Configuration (Detailed):

4. Who can CREATE?
   - Minimum role: [owner/admin/manager/member]
5. Who can UPDATE?
   - Minimum role: [owner/admin/manager/member]
   - Can users update their own records? (self-edit)
6. Who can DELETE?
   - Minimum role: [owner/admin/manager/member]
7. Custom organization_lookup?
   - Default: 'organization_id'
   - Custom: [ex: 'team__organization_id' for TeamMember]
8. Any special permission logic?
   - [describe any non-standard rules]
```

If no, use sensible defaults:
- Create: Same as Write
- Update: Same as Write
- Delete: Admin+
- organization_lookup: Default
- Special logic: None

### Phase 2 — Generate Permission Class

Based on answers, generate the permission class. Use the reference template from `references/permission-template.py`.

**Role patterns:**

| Pattern | has_permission | has_object_permission |
|---------|---------------|----------------------|
| Owner-only | `auth_member.has_owner_permission` | Same |
| Admin+ | `auth_member.has_admin_permission` | Same |
| Manager+ | `auth_member.has_manager_permission` | Same |
| Member (self) | `auth_member.has_member_permission` | `obj.user_id == auth_user.id` |
| Admin-delete | Safe methods: all; Write: admin+ | Same |

**Generate and present:**

```python
# apps/{app}/permissions.py — append this class

from django.contrib.auth import decorators
from rest_framework import permissions

from apps.accounts.permissions.generics import OrganizationScopedPermission, IsActiveMember
from apps.accounts.utils.requests import get_member


class {Resource}Permission(OrganizationScopedPermission):
    \"\"\"
    Permission for {Resource}.
    - Read: all authenticated members
    - Write: {role}+
    \"\"\"

    organization_lookup = '{lookup}'

    def has_permission(self, request, view):
        auth_member = get_member(request)
        return super().has_permission(request, view) and (
            request.method in permissions.SAFE_METHODS
            or (auth_member and auth_member.has_{role}_permission)
        )

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        auth_member = get_member(request)
        if not auth_member:
            return False
        return auth_member.has_{role}_permission
```

Wait for user confirmation before proceeding.

### Phase 3 — Insert into File

1. Read `apps/{app}/permissions.py`
2. Append the new class at the end
3. Verify imports are present (add if missing)
4. Show the diff

---

## Anti-patterns

- **Do not bypass `super().has_object_permission()`.** The organization scope check is mandatory
- **Do not forget `get_member(request)` check.** Members can be None if session is invalid
- **Do not hardcode role strings.** Use `has_{role}_permission` properties on the Member model
- **Do not skip `has_permission` for write operations.** Object-level checks don't apply to list/create

---

## Example Permission Class

### Input
- Resource: Project
- Read: all authenticated
- Create: manager+
- Update: owner only
- Delete: admin+

### Output
```python
# apps/teams/permissions.py

from rest_framework import permissions

from apps.accounts.permissions.generics import OrganizationScopedPermission
from apps.accounts.utils.requests import get_member


class ProjectPermission(OrganizationScopedPermission):
    """
    Permission for Project.
    - Read: all authenticated members
    - Create: manager+
    - Update: owner only
    - Delete: admin+
    """

    organization_lookup = "team__organization_id"

    def has_permission(self, request, view):
        auth_member = get_member(request)
        if request.method in permissions.SAFE_METHODS:
            return super().has_permission(request, view)
        if not auth_member:
            return False
        if request.method == "POST":
            return auth_member.has_manager_permission
        if request.method in ("PUT", "PATCH"):
            return auth_member.has_owner_permission
        if request.method == "DELETE":
            return auth_member.has_admin_permission
        return False

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        auth_member = get_member(request)
        if not auth_member:
            return False
        if request.method in ("PUT", "PATCH"):
            return obj.created_by_id == auth_member.user_id
        return auth_member.has_admin_permission
```
