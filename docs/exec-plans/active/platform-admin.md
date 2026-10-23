# Execution Plan: Platform Admin Panel (API)

## Table of Contents

- [Status](#status)
- [Context](#context)
- [Goal](#goal)
- [Approach](#approach)
- [Progress Log](#progress-log)
- [Decisions](#decisions)
- [Done Criteria](#done-criteria)

---

## Status

- [x] Active
- [ ] Completed
- [ ] Cancelled

---

## Context

Root feature `specs/platform-admin/` (track L: product, UX, UI baseline Penpot #13, tech contract approved
2026-10-22) and [ADR-009](../../../../docs/adr/009-platform-access-outside-organization-context.md). Implementation
spec: `specs/platform-admin.md`; Frontend sibling: `../CrewForge-Frontend/specs/platform-admin.md`; test plan:
`specs/platform-admin/test-plan.md` (root).

---

## Goal

Platform staff operate Organizations and Users through `/api/platform/` without database or Django admin access;
suspension, blocking, revocation and read-only "view as" are enforced server-side; every staff action is audited;
the `is_superuser` shortcut is gone. All AC-1…AC-28 API tests of the test plan pass.

---

## Approach

### Phase 0: Superuser shortcut removal (PR A)

- [x] `Member.has_owner_permission` and StoredFile permission/view/serializer without `is_superuser`
- [x] Regression tests (AC-7); release note: grant `platform_role=admin` to operators before deploy

### Phase 1: Increment 1 — read panel (PR B)

- [x] Choices, `User.platform_role`, `Organization.status` + suspension fields, migration
- [x] `set_platform_role` command, Django admin, `user.platform_role_changed`
- [x] `apps/platform`: permissions, querysets, filters, serializers, overview service, read views, urls
- [x] Session payload fields (`ErrorCode` values move to Phase 2, where they are first raised)
- [x] Tests (AC-1…AC-6), schema, `make sync-docs`

### Phase 2: Increment 2 — actions and enforcement (PR C)

- [ ] `User.blocked_*`, `sessions_revoked_at`, `revoke_sessions`
- [ ] Authentication and sign-in checks; Organization context, login and Invitations refuse suspended Organizations
- [ ] Action services + endpoints + emails (on commit)
- [ ] Tests (AC-8…AC-21, AC-28), schema, `make sync-docs`

### Phase 3: Increment 3 — impersonation (PR D)

- [ ] `Impersonation` model, start/exit services and endpoints, session payload
- [ ] Authentication swap, `DenyWritesWhileImpersonating`, logout, Organization login without `last_login_at`
- [ ] Tests (AC-22…AC-27), schema, `make sync-docs`

### Phase 4: Docs

- [ ] `docs/security.md`, `docs/frontend-integration-guide.md`, `docs/architecture.md`, `docs/product-sense.md`, `AGENTS.md`

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-10-22 | Plan created (stage 5, `implementation-planner`) |
| 2026-10-22 | Phase 1 (PR B) done: platform role, Organization status, read-only `/api/platform/` (overview, Organizations + tabs, Users, audit), session fields, admin/command audited, docs |
| 2026-10-22 | Phase 0 done: shortcuts removed; Django admin validates StoredFiles with `StoredFileAdminSerializer`; code review clean; 1606 tests pass |

---

## Decisions

| Decision | Rationale | Alternatives considered |
|----------|-----------|------------------------|
| Server-side impersonation in the Django session | ADR-009, Q71 | JWT for the target |
| `sessions_revoked_at` + blacklist | BR-21: refuse already-issued access tokens at once | Blacklist only (access tokens live 15 min) |
| `User.blocked_*` fields (data only) moved to Phase 1 | The read panel shows blocked Users, the Blocked mark/filter and the overview tile; enforcement stays in Phase 2 | Add them with enforcement in Phase 2 |
| Overview and querysets in `apps/platform/selectors.py` | Same pattern as `apps/dashboard/selectors.py` | `services.py` |
| `set_platform_role` in `apps/accounts/utils/platform_role.py` | `apps/accounts` (admin, command) must not import `apps/platform` | Service in `apps/platform` |
| List ordering parameter is `order_by` (project convention); filter-options only on the platform audit (action labels for the Action filter) | Existing lists use `order_by`; platform enums are in the schema | `ordering`; options routes now |
| `options_component_prefix` on `OptionsBaseModelMixin`; scoped paginated options share the canonical schema component | Two ViewSets of `AuditEvent` exposed options with the same component names (spectacular warnings, wrong schema) | Rename per filterset class (unstable: orderable filtersets are generated) |
| One service function per action | Single transaction, reused by views and tests | Logic in views |
| `StoredFileAdminSerializer` for the StoredFile admin form | ADR-009 keeps Django admin access unchanged while the API serializer has no admin case | Context flag in the API serializer (review finding) |

---

## Done Criteria

- [ ] AC-1…AC-28 API tests of `specs/platform-admin/test-plan.md` written and passing
- [ ] Every platform route has a role-`none` test; every write family has an impersonation test
- [ ] Tests pass (`make l_test`)
- [ ] Lint passes (`make l_format_code`)
- [ ] Schema regenerated if API changed (`make l_spectacular`)
- [ ] `docs/frontend-integration-guide.md` updated if request/response changed
