# Execution Plan: Security Hardening

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

A security review found a forgeable secret key fallback, stored XSS through file downloads, unvalidated uploads, a fail-open default permission, public diagnostics, tokens readable by JavaScript in the SPA, missing auth throttling, unverified emails trusted by invitations and other hardening gaps.

- PO spec: `specs/security-hardening.md` (monorepo root)
- Delivery 1 spec: `specs/security-hardening-critical.md`

---

## Goal

Every risk R1–R17 of the PO spec is fixed or explicitly accepted, each delivery released only after a `/code-review` round with zero findings.

---

## Approach

### Delivery 1: API critical fixes (R1, R3, R4, R8, R9)

- [x] Secret key validation, optional JWT signing key
- [x] Attachment policy + `nosniff` + sandbox CSP for file downloads
- [x] Upload size limit and content detection by signature
- [x] `IsAuthenticated` default + public routes allowlist test
- [x] `session/config` diagnostics only with `DEBUG`
- [ ] Review loop until zero findings

### Delivery 2: Browser session in HttpOnly cookies (R2, R6, R11, R12, R13)

- [ ] `JWTCookieAuthentication` + CSRF, cookie issuers, refresh/logout via cookie
- [ ] Auth throttling, revocation on password change, `SameSite=Lax`, session key rotation
- [ ] Frontend + nginx headers (Frontend repo)

### Delivery 3: Identity and invitations (R5, R7)

- [ ] Email verification; invitations by email require a verified email
- [ ] Uniform, asynchronous password reset

### Delivery 4: Operational hardening (R10, R14–R17)

- [ ] API docs/admin restrictions, HSTS, dependency scanning, security logging, infra guidance

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-10-07 | Plan created; Delivery 1 implemented |

---

## Decisions

| Decision | Rationale | Alternatives considered |
|----------|-----------|------------------------|
| Signature sniffing in Python | Small allowlist, no native dependency | `python-magic` |
| Raster images are the only inline types | SVG/HTML can run script on the API origin | Inline by `download` flag |
| `StoredFile.save()` keeps an existing `content_type` | The validated (sniffed) type must not be replaced by a filename guess | Recompute on every save |

---

## Done Criteria

- [ ] All four deliveries merged
- [ ] Tests pass (`make l_test`)
- [ ] Lint passes (`make l_format_code`)
- [ ] Schema regenerated if API changed (`make l_spectacular`)
- [ ] `docs/frontend-integration-guide.md` updated if request/response changed
