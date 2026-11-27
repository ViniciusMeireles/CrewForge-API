# Execution Plan: Billing and Plans · Increment 2 (Payments)

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

Increment 2 of `specs/billing-and-plans/` (root): payments through Asaas behind a gateway interface (ADR-014). Contract:
`specs/billing-and-plans/tech.md` › Increment 2 (approved 2026-11-27). Implementation spec:
`specs/billing-and-plans-payments.md`. Design baseline: Penpot PR #27 · revn 898.

---

## Goal

Owners change, cancel and resume paid Plans and pay on the Asaas page; Invoices, webhooks and reconciliation keep the
state in step with the gateway; trials end, courtesy Subscriptions become trials; `make check` passes and the schema is
synced to the Frontend.

---

## Approach

### Phase 1: Models, migrations, gateway

- [x] Choices, `Subscription` fields, `Invoice`, `BillingProfile`, `GatewayEvent`, validators, admin, factories
- [x] Migrations `0004_payments`, `0005_courtesy_to_trial`
- [x] `gateways/` (`base`, `asaas`, `fake`), settings, production check

### Phase 2: Services and endpoints

- [x] Pricing; profile, preview, change, cancel, resume, discard; `sync_invoice`
- [x] `BILLING_MANAGE`, permissions, serializers, views, URLs, webhook authentication; platform 409 (BR-36)

### Phase 3: Tasks and emails

- [x] Event processing, reconciliation, period end, trial expiry and reminders; beat
- [x] Emails and templates; audit actions; error codes

### Phase 4: Docs, schema, sandbox

- [x] `django.po`, integration guide, `security.md`, `product-sense.md`, `example.env`, `AGENTS.md`
- [x] `make l_spectacular`; root `make sync-docs` after merge
- [ ] Sandbox run with the user's keys; TQ-2 recorded in `tech.md`

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-11-27 | Plan created |
| 2026-11-27 | Phases 1–4 implemented (models, gateway, services, endpoints, tasks, emails, docs); sandbox run pending |

---

## Decisions

| Decision | Rationale | Alternatives considered |
|----------|-----------|------------------------|
| Hosted pages with `billingType = UNDEFINED` | No card data (BR-22); works for Pix, boleto and card (ADR-014) | Recurring card with tokenization |
| Standard library HTTP client for Asaas | No new dependency for a handful of endpoints | `httpx`, `requests` |

---

## Done Criteria

- [ ] Every increment 2 row of `specs/billing-and-plans/test-plan.md` with an API test is written and passing
- [ ] Tests pass (`make l_test`)
- [ ] Lint passes (`make l_format_code`), types pass (`make l_typecheck`)
- [ ] Schema regenerated (`make l_spectacular`)
- [ ] `docs/frontend-integration-guide.md` updated
