# Design Decisions Index

Catalog of architectural and design decisions made in CrewForge.
Each entry captures the context, decision, and consequences.

---

## Table of Contents

- [Session-Based Organization Context](#session-based-organization-context)
- [Soft-Delete Pattern](#soft-delete-pattern)
- [4-Level Role Hierarchy](#4-level-role-hierarchy)
- [Organization-Scoped Permissions](#organization-scoped-permissions)
- [Custom PrimaryKeyRelatedField](#custom-primarykeyrelatedfield)
- [Schema Facade Pattern](#schema-facade-pattern)
- [Modular Test Structure](#modular-test-structure)
- [Email Subsystem](#email-subsystem)

---

## Session-Based Organization Context

**Date:** 2025-01 (initial design)

**Context:** CrewForge needs a way to scope API requests to a specific
organization. JWT tokens are stateless and can't carry mutable server-side
state. The organization context must be verified against the database on every
request.

**Decision:** Use Django sessions to store `organization_id`. The 3-step auth
flow authenticates the user (JWT), lists organizations, then sets the session
context via a dedicated login endpoint.

**Consequences:**
- Positive: Server-side state can be invalidated, verified per-request
- Positive: Clear separation between authentication (JWT) and authorization context (session)
- Negative: Requires session middleware and cookie handling
- Negative: SPA integration requires CORS + SameSite cookie configuration

---

## Soft-Delete Pattern

**Date:** 2025-01 (initial design)

**Context:** Domain models need deactivation without data loss. Cascading hard
deletes would break referential integrity across organizations.

**Decision:** All domain models inherit `BaseModel` with `is_active` field.
`ModelViewSetMixin.perform_destroy()` calls `instance.inactivate()` instead of
`instance.delete()`. Querysets filter by `is_active=True` by default.

**Consequences:**
- Positive: Preserves FK references, enables undo
- Positive: Consistent pattern across all models
- Negative: List endpoints exclude inactive records (requires `filter_inactives()` to see them)
- Negative: Unique constraints must account for soft-deleted records

---

## 4-Level Role Hierarchy

**Date:** 2025-01 (initial design)

**Context:** The invitation system needs role-scoped visibility: admins should
see manager and member invitations, owners should see all. Three levels
(Admin, Manager, Member) couldn't express the owner-admin distinction cleanly.

**Decision:** 4-level hierarchy: Owner > Admin > Manager > Member. Enforced
at permission layer (`has_owner_permission`, `has_admin_permission`,
`has_manager_permission`), serializer layer (`ValidateRoleSerializerMixin`),
and queryset layer (invitation filtering).

**Consequences:**
- Positive: Clean separation of invitation visibility
- Positive: Matches real organizational structures
- Negative: More complex permission checks
- Negative: Role changes require hierarchy validation

---

## Organization-Scoped Permissions

**Date:** 2025-01 (initial design)

**Context:** Resources belong to organizations. Cross-organization access
must be denied. The permission system needs to verify both authentication and
organization membership.

**Decision:** `OrganizationScopedPermission` extends `IsActiveMember` with
`organization_lookup` for FK traversal. `has_object_permission()` calls
`is_same_organization_scope()` to verify the object belongs to the session
organization.

**Consequences:**
- Positive: Single base class for all org-scoped permissions
- Positive: FK traversal via `organization_lookup` (e.g., `team.organization_id`)
- Negative: Must override `organization_lookup` for nested resources
- Negative: Cross-org returns 404 (not 403) to prevent enumeration

---

## Custom PrimaryKeyRelatedField

**Date:** 2025-01 (initial design)

**Context:** DRF's default `PrimaryKeyRelatedField` doesn't filter by
`is_active` or organization scope. Serializer fields can return references to
inactive or cross-org records.

**Decision:** Custom `PrimaryKeyRelatedField` combines
`PrimaryKeyActiveRelatedFieldMixin` (filters `is_active=True`) with
`PrimaryKeyOrganizationRelatedFieldMixin` (filters by `organization_id`).
Used as `serializer_related_field` in `ModelSerializerMixin`.

**Consequences:**
- Positive: Automatic filtering in all FK fields
- Positive: Consistent behavior across all serializers
- Negative: Must ensure related models have `is_active` and `organization_id`
- Negative: Can't use default DRF `PrimaryKeyRelatedField` directly

---

## Schema Facade Pattern

**Date:** 2025-01 (initial design)

**Context:** Every ViewSet needs `@extend_schema` decorators for all 7
standard actions. Repeating this for every viewset leads to boilerplate and
inconsistency.

**Decision:** `extend_schema_model_view_set()` decorator auto-generates schema
annotations for all standard actions (retrieve, list, create, destroy, update,
partial_update, choices) from the model's `verbose_name`.

**Consequences:**
- Positive: One decorator replaces 7 individual ones
- Positive: Consistent API documentation
- Negative: Custom actions need additional `@extend_schema` on top
- Negative: Model must have proper `verbose_name` in `Meta`

---

## Modular Test Structure

**Date:** 2025-01 (initial design)

**Context:** Flat test files with monolithic test classes became hard to
navigate as test counts grew. Finding the test for a specific behavior
required scrolling through hundreds of lines.

**Decision:** One directory per resource (`test_{resource}/`) with one file
per concern: `test_model.py`, `test_serializer.py`, `test_crud.py`,
`test_permission.py`, `test_filter.py`, `test_choices.py`,
`test_integration.py`.

**Consequences:**
- Positive: Single responsibility per test file
- Positive: Faster navigation to relevant tests
- Positive: Easy parallel test execution
- Negative: More files to manage
- Negative: Requires discipline to maintain the pattern

---

## Email Subsystem

**Date:** 2025-01 (initial design)

**Context:** Multiple email types (password reset, invitation) share common
composition patterns (template rendering, CTA buttons, attachments). Each
email needs preview support for development.

**Decision:** `EmailBase` template method class with `get_message()` builder,
`CTAEmail` helper, and `EmailView` for preview. Concrete emails subclass and
override attributes/methods.

**Consequences:**
- Positive: Consistent email format across the application
- Positive: Preview support without sending emails
- Positive: Builder pattern for complex email composition
- Negative: Template method chain can be hard to follow
- Negative: Each new email type requires a new subclass
