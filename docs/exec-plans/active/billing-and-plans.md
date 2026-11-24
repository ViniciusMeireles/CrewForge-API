# Execution Plan: Billing and Plans · Increment 1

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

Increment 1 of `specs/billing-and-plans/` (root): Plans, Subscriptions, limits and the Audit gate, without payments.
Contract: `specs/billing-and-plans/tech.md` (approved 2026-11-24). Implementation spec: `specs/billing-and-plans.md`.
Decision: ADR-013 (root `docs/adr/`).

---

## Goal

Every Organization has a Subscription; limits are refused with `PLAN_LIMIT_REACHED` at every creation point; Audit
follows the Plan; the billing read endpoints, the session summary and the platform plan change are live; the purge is
ready behind its setting; `make check` passes and the schema is synced to the Frontend.

---

## Approach

### Phase 1: App, models, migrations

- [ ] `apps/billing` app, choices, catalog, `Plan`, `Subscription`, admin, factories (`OrganizationFactory` gains a Subscription)
- [ ] Migrations `0001`–`0003`, `ensure_subscriptions` command, migration tests

### Phase 2: Subscription start and access gates

- [ ] `start_subscription` on Organization creation, `trial_started` event, concurrency test
- [ ] `access.py` `BILLING_READ`, `FEATURE_REQUIRED`, `plan_allows`; session `access.billing` and `subscription`; `select_related`
- [ ] Error codes; `AuditEventPermission` → `PLAN_FEATURE_UNAVAILABLE`

### Phase 3: Limits

- [ ] Selectors and `ensure_within_limit`
- [ ] Invitation create, accept/Readmission, `create-with-invite`, Team, StoredFile and organization image; matrix rows

### Phase 4: Endpoints

- [ ] `GET /api/billing/plans/`, `GET /api/billing/subscription/`
- [ ] Platform `change_plan` and detail `subscription`

### Phase 5: Purge, docs, schema

- [ ] Purge queryset method, task, beat, setting
- [ ] `django.po`, integration guide, `security.md`, `product-sense.md`, `example.env`, `AGENTS.md`
- [ ] `make l_spectacular`; pre-deploy counts in the PR; root `make sync-docs` after merge

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-11-24 | Plan created |

---

## Decisions

| Decision | Rationale | Alternatives considered |
|----------|-----------|------------------------|
| Entitlements as a code catalog with JSON values | ADR-013 | Columns per Entitlement; Entitlement table |
| Purge behind `AUDIT_RETENTION_PURGE_ENABLED` | The first run is irreversible; enabled after the pre-deploy count and a backup | Purge on by default |

---

## Done Criteria

- [ ] Every row of `specs/billing-and-plans/test-plan.md` with an API test is written and passing
- [ ] Tests pass (`make l_test`)
- [ ] Lint passes (`make l_format_code`), types pass (`make l_typecheck`)
- [ ] Schema regenerated if API changed (`make l_spectacular`)
- [ ] `docs/frontend-integration-guide.md` updated if request/response changed
