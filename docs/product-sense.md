# Product Sense

This document captures the design beliefs, domain rationale, and non-goals
that shape CrewForge. Agents should consult this before making architectural
or product decisions.

---

## Table of Contents

- [Core Beliefs](#core-beliefs)
- [Domain Model](#domain-model)
- [Design Decisions](#design-deisions)
- [Non-Goals](#non-goals)
- [Analogies](#analogies)

---

## Core Beliefs

1. **Organization-aware access control is the heartbeat.** Every protected
   resource belongs to an organization. The session-based organization context
   (`organization_id` in the Django session) is the primary scoping mechanism.

2. **JWT alone is not "logged in."** A JWT authenticates the user, but the
   organization context must be established separately via
   `POST /api/accounts/organizations/{id}/login/`. Agents must never assume
   that obtaining a JWT is enough.

3. **Soft-delete over hard-delete.** Most domain models use `is_active` for
   soft-deletion. This preserves referential integrity, enables undo, and
   simplifies audit trails. Only `StoredFile` performs hard deletes (physical
   file removal).

4. **Role hierarchy is sacred.** Owner > Admin > Manager > Member. This
   hierarchy is enforced at the permission layer, serializer layer, and
   queryset layer. Changing role logic requires tests and careful review.

5. **Parse, don't validate.** We parse data shapes at system boundaries
   (serializers, permissions) rather than validating ad-hoc throughout the
   codebase. This makes constraints explicit and machine-checkable.

6. **Boring technology wins.** We favor well-understood, composable libraries
   (Django, DRF, django-filter, simplejwt) over trendy alternatives. Agents
   can reason about boring tech more reliably because of training set
   representation and API stability.

7. **Repository-local knowledge only.** Anything not in the codebase does not
   exist for agents. Design decisions, architectural rationale, and product
   principles must be encoded in markdown or code.

---

## Domain Model

### Organization

A workspace or tenant. Every member, team, invitation, and file belongs to one
organization. Organizations have owners, profiles, and images.

### Member

A user's membership within an organization. A single `User` can be a `Member`
of multiple organizations, each with an independent role. The `Member` is the
unit of permission checking.

### Role Hierarchy

```
Owner   — full control, can modify any member, manage billing (future)
Admin   — can manage members, invitations, teams
Manager — can manage teams, limited member operations
Member  — basic access, can update own record
```

### Team

A grouping within an organization. Teams have their own role hierarchy
(Owner, Admin, Member) independent of the org-level role. A `TeamMember`
links a `Member` to a `Team` with a team-level role.

### Invitation

An email-based invite to join an organization. Invitations are role-scoped:
admins see MANAGER+MEMBER invites, owners see all roles. Invitations have
expiry, acceptance status, and a 60-second email cooldown.

### StoredFile

A file uploaded by a user. Files have granular access levels (`PUBLIC`,
`OWNER`, `MEMBERS_ORGANIZATION`, etc.) via `StoredFileAccess` enum. Files
provide absolute download URLs via `SELF_URL`.

### OrganizationProfile / OrganizationImage

Extended metadata for an organization. Profile holds website/description.
Images (LOGO, COVER) reference `StoredFile` records.

---

## Design Decisions

### Why session-based organization context?

JWT tokens are stateless and can't carry mutable server-side state. The
organization context needs to be verified against the database (is the user
still an active member?). The Django session provides a server-side store that
can be invalidated, rotated, and verified on every request.

### Why soft-delete?

- Preserves foreign key references (no cascading hard deletes)
- Enables undo/reactivate workflows
- Simplifies audit trails (`is_active` changes are tracked)
- Consistent pattern across all domain models

### Why 4-level role hierarchy?

Three levels (Admin, Manager, Member) were insufficient for the invitation
scoping problem: admins should invite managers and members, but only owners
should invite other admins. The 4-level hierarchy (Owner, Admin, Manager,
Member) provides clean separation of concerns.

### Why `gettext_lazy` everywhere?

User-facing strings (error messages, schema descriptions, email content) use
`gettext_lazy` to support future i18n. This is a project-wide convention.

---

## Non-Goals

CrewForge is **not**:

- A general-purpose SaaS multi-tenant platform
- An OAuth/OpenID Connect provider
- A file storage service (it uses local filesystem, not S3)
- A workflow engine or task scheduler
- A real-time communication system (no WebSockets)

CrewForge **is**:

- A Django REST API for organization management
- An invitation-based team management system
- A file management layer with granular permissions
- A reference implementation of organization-aware access control

---

## Analogies

| CrewForge concept | Real-world analogy |
|---|---|
| Organization | A company workspace (like Slack workspace) |
| Member | A user's membership in that workspace |
| Role | Permission level within the workspace |
| Team | A channel or project group within the workspace |
| Invitation | An email invite to join the workspace |
| StoredFile | A file uploaded to the workspace's drive |
