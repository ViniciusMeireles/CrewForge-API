# Execution Plan: Audit Trail

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

The API keeps no queryable record of who changed what: `log_security_event` only writes text to
stdout, and `BaseModel` keeps only the last `updated_by`. This is the first of three SaaS-foundation
features (audit → platform admin → billing). The other two record their events through this one.

- Root PO spec: `../specs/audit-trail.md`
- Backend spec: `specs/audit-trail.md`
- Frontend spec: `../CrewForge-Frontend/specs/audit-trail.md`

---

## Goal

- Every write in the event catalog and every persisted security event creates exactly one immutable
  `AuditEvent`, in the same transaction as the operation.
- Owner and Admin list and filter their Organization's events at `GET /api/audit/events/`, and see
  `member.access.audit = true`.
- Users read their own account events at `GET /api/accounts/users/me/activity/`.
- No existing response body or status code changes.

---

## Approach

### Phase 1: Recording layer

- [x] Move `client_ip` to `apps/generics/utils/requests.py` (re-export it from `security_log`)
- [x] Create `apps/audit` (app config, `LOCAL_APPS`)
- [x] Choices: `AuditActionChoices`, `AuditActorTypeChoices`, `ACCOUNT_ACTION_PREFIXES`
- [x] `AuditEvent` model (immutable), queryset/manager, indexes, migration
- [x] `services.py`: `snapshot_instance`, `diff_instance`, `record_audit_event` + unit tests

### Phase 2: Hooks and catalog wiring

- [x] `ModelViewSetMixin`: `audit_actions`, `audit_exclude_fields`, atomic `perform_*` hooks
- [x] Declare `audit_actions` on the 8 ViewSets; `OrganizationViewSet.get_audit_organization_id`
- [x] Explicit recording: `send_email`, `accept` (log moved inside atomic + `member.joined`),
  `decline`, `UserProfileViewSet.partial_update`
- [x] Recording tests per domain (including no-op, failed write and rollback on event failure)

### Phase 3: Security events

- [x] `log_security_event` persists events listed in `AuditActionChoices`
- [x] Security-log tests (persisted vs stdout-only, failure events stored after 4xx, no email)

### Phase 4: Read API

- [x] `Member.has_audit_access` + `MemberAccessSerializer.audit`
- [x] Permission, serializer, filter, ViewSet, URLs, read-only admin, factory
- [x] `users/me/activity/`
- [x] `test_audit_event/` matrix + account activity tests + query-count test

### Phase 5: Docs and release

- [x] pt-BR catalog
- [x] `make l_spectacular`
- [x] `frontend-integration-guide.md`, `security.md`, `architecture.md`, `product-sense.md`
- [x] ADR amendment (append-only exception) in the root repository (root PR)
- [x] Root `make sync-docs`, then hand over to the Frontend plan

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-10-15 | Plan created |
| 2026-10-15 | Phases 1–4 implemented on `feat/audit-trail`; docs and pt-BR catalog updated; 1588 tests pass (baseline 1486), schema regenerated without warnings. Pending: commit/PR, ADR amendment (root), `make sync-docs` after merge |
| 2026-10-16 | Merged in #46 (Codacy findings fixed in the PR); `make sync-docs` run and Frontend implemented in CrewForge-Frontend#35; follow-up drops `is_active` from snapshots (create events listed it as a change); ADR-004 amendment in the root repository |

---

## Decisions

| Decision | Rationale | Alternatives considered |
|----------|-----------|------------------------|
| Declarative `audit_actions` in `ModelViewSetMixin` | Keeps recording explicit per ViewSet (Q5) without duplicating `perform_*` overrides | Signals (implicit, miss request context); hand-written calls in every ViewSet |
| Synchronous write in the same transaction | PO decision Q5: no change without its record | Celery (can lose events), `on_commit` (event can be lost after commit) |
| `AuditEvent` outside `BaseModel` | Append-only; soft delete is meaningless | Inherit `BaseModel` and ignore `is_active` |
| `subject_user` field | Account activity needs the owner of failed-login events, whose actor is anonymous | Derive from `actor_user` (fails for `auth.login.failed`) |
| Explicit `actor_member` in `record_audit_event`; a session Member of another Organization is ignored | On acceptance and `create-with-invite` the session Member (if any) belongs to another Organization or does not exist | Always use the session Member (wrong actor) |
| Acceptance keeps its stdout line (`invitation.accepted` or `member.readmitted`) and audits the other event without logging it | Existing security-log contract (readmission logs only `member.readmitted`) | Log both events to stdout |
| Failed sign-in linked to the targeted account in the database only | Account activity must show failed attempts, while the log line keeps `user_id` empty | Put `user_id` in the log line too |
| Model property named `audit_label` | `Member` querysets already annotate `label` (options) | `label` (collides with the annotation) |
| Audit ViewSet is a `ModelViewSet` limited to `get`/`options` | `filter-options/` is only generated for `ModelViewSet` subclasses | `ReadOnlyModelViewSet` (no options route) |

---

## Done Criteria

- [x] Every catalog action covered by a recording test
- [x] Existing suite unchanged and green (only the `member.access` key list tests gained `audit`)
- [x] Tests pass (`make l_test`)
- [x] Lint passes (`make l_format_code`)
- [x] Schema regenerated if API changed (`make l_spectacular`)
- [x] `docs/frontend-integration-guide.md` updated if request/response changed
