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

- [x] `User.blocked_*`, `sessions_revoked_at`, `revoke_sessions`
- [x] Authentication and sign-in checks; Organization context, login and Invitations refuse suspended Organizations
- [x] Action services + endpoints + emails (on commit)
- [x] Tests (AC-8…AC-21, AC-28), schema (`make sync-docs` after merge)

### Phase 3: Increment 3 — impersonation (PR D)

- [x] `Impersonation` model, start/exit services and endpoints, session payload
- [x] Authentication swap, read-only enforcement, logout, Organization login without `last_login_at`
- [x] Tests (AC-22…AC-27), schema (`make sync-docs` after merge)

### Phase 4: Docs

- [ ] `docs/security.md`, `docs/frontend-integration-guide.md`, `docs/architecture.md`, `docs/product-sense.md`, `AGENTS.md`

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-10-22 | Plan created (stage 5, `implementation-planner`) |
| 2026-10-22 | Phase 1 (PR B) done: platform role, Organization status, read-only `/api/platform/` (overview, Organizations + tabs, Users, audit), session fields, admin/command audited, docs |
| 2026-10-22 | Phase 0 done: shortcuts removed; Django admin validates StoredFiles with `StoredFileAdminSerializer`; code review clean; 1606 tests pass |
| 2026-10-27 | Phase 3 (PR D) built: `Impersonation`, start/exit, authentication swap and read-only enforcement, session payload, logout and blocking end it, pt-BR |
| 2026-10-23 | Phase 2 (PR C) built: blocking/revocation at authentication, suspension enforcement, eight admin actions with audit and owner emails, pt-BR |

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
| Coded exceptions (`apps/generics/errors.py`: `InvalidState`, `CooldownThrottled`; `apps/accounts/exceptions.py`: `AccountBlocked`, `OrganizationSuspended`) read by the exception handler (`error_code`, `error_details`) | One envelope for the new codes; outside `exceptions.py` because `rest_framework.views` imports the authentication classes (circular import) | Ad-hoc `Response` bodies as in the invitation cooldown |
| Suspension checked in `OrganizationScopedRequestMixin.check_permissions` with per-view `organization_context_exempt_actions` | Every Organization-context view already uses the mixin; runs before the permissions so the code is `ORGANIZATION_SUSPENDED`, not `PERMISSION_DENIED`; `get_member` memoized per request so the status query runs only without a Member (no extra query on the normal path) | A global DRF permission (views override `permission_classes`); raising inside `get_organization_id` (breaks audit and platform actions of staff Members) |
| Revocation checked before blocking in `JWTCookieAuthentication.get_user` (refines `tech.md`'s order) | Every token of a blocked User predates the block, so a stale cookie becomes anonymous instead of failing logout and public routes with `ACCOUNT_BLOCKED` (review finding); the SPA only needs `ACCOUNT_BLOCKED` at sign-in | `tech.md` order (blocked first) |
| Blocked sign-in through `USER_AUTHENTICATION_RULE` | simplejwt calls it only after the password or refresh token is accepted (BR-22), in sign-in and refresh | Override `TokenObtainPairSerializer.validate` (tokens already issued by then) |
| Org/User platform viewsets on `ReadOnlyModelViewSet` + `post` for the actions | `POST` on the lists stays `405` (no `create`) | `ModelViewSet` with `post` allowed |
| Read-only enforced in `ImpersonationAuthentication` (allow-list by resolved view name) instead of a `DenyWritesWhileImpersonating` permission class | One place for every DRF view; a permission class would have to be added to each view that overrides `permission_classes` (refines the spec) | Global permission class + per-view additions |
| Impersonation authentication lives in `apps/platform` and is the default class | `apps/accounts` must not import `apps/platform` | Swap inside `JWTCookieAuthentication` |
| Logout ends the impersonation through Django's `user_logged_out` signal | Same layering rule; `LogoutView` stays in `apps/accounts` | Import platform services in the view |
| An expired leftover (session lost) is ended when the staff member starts a new one; a staff member who loses the platform role has the session ended | Avoid a 30-minute lock-out; no viewing without the role | Refuse until it expires |
| One active impersonation per staff member is protected by a partial unique constraint | BR-27 under concurrency | Application check only |
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
