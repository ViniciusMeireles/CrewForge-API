# Execution Plan: Permission-Based Navigation — Member Access in Session

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

- [ ] Active
- [x] Completed
- [ ] Cancelled

---

## Context

The frontend decides which management areas a Member sees from a static menu, which already drifted from the API (Invitations shown to MANAGER/MEMBER, who get `403`). The backend must expose area access in the session.

- PO spec: `CrewForge/specs/permission-based-navigation.md` (monorepo root)
- Backend spec: `specs/permission-based-navigation.md`
- Frontend spec: `CrewForge-Frontend/specs/permission-based-navigation.md`

---

## Goal

`GET /api/accounts/session/` and `POST /api/accounts/organizations/{id}/login/` return `member.access` (`members`, `invitations`, `teams`, `organization_settings`) matching the Role matrix, with no extra queries, and `InvitationPermission` uses the same predicate.

---

## Approach

### Phase 1: Access predicates

- [x] Add `has_members_access`, `has_invitations_access`, `has_teams_access`, `has_organization_settings_access` to `Member`
- [x] Unit tests: Role matrix, superuser, inactive

### Phase 2: Serializer

- [x] `MemberAccessSerializer` + `access` in `MemberSessionSerializer`
- [x] Serializer + integration tests (session, org login, Role change, query count)

### Phase 3: Permission alignment

- [x] `InvitationPermission.has_permission` → `has_invitations_access`
- [x] Consistency tests (access vs list endpoints); existing invitation tests green

### Phase 4: Schema and docs

- [x] `make l_spectacular`
- [x] `docs/frontend-integration-guide.md` §3.6
- [x] `make sync-docs` (root)

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-10-06 | Plan created |
| 2026-10-06 | Phases 1–4 implemented; 1214 tests pass; schema regenerated; docs synced to Frontend |
| 2026-10-07 | Review fixes: `MemberPermission` and `TeamPermission` reuse `has_members_access` / `has_teams_access` on reads |
| 2026-10-07 | Merged in #22; plan completed |

---

## Decisions

| Decision | Rationale | Alternatives considered |
|----------|-----------|------------------------|
| Access predicates as `Member` properties | Reusable by permission classes; same pattern as `has_*_permission` | `SerializerMethodField` in the session serializer |
| No server-side cache | Cheap to compute; cache would keep revoked access alive | Django cache / Redis with invalidation on Role change |
| Organization settings OWNER only | Confirmed by PO despite ADMIN+ writes on profile/images | ADMIN+ |

---

## Done Criteria

- [x] `member.access` returned by session and org login endpoints
- [x] Role matrix, superuser, inactive, cross-org covered by tests
- [x] Session endpoint query count unchanged
- [x] Tests pass (`make l_test`)
- [x] Lint passes (`make l_format_code`)
- [x] Schema regenerated if API changed (`make l_spectacular`)
- [x] `docs/frontend-integration-guide.md` updated if request/response changed
