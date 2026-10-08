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
- [x] Review loop until zero findings (4 rounds: 5 + 5 + 1 findings fixed, then clean)

### Delivery 2: Browser session in HttpOnly cookies (R2, R6, R11, R12, R13)

- [x] `JWTCookieAuthentication` + CSRF, cookie issuers, refresh/logout via cookie
- [x] Auth throttling, revocation on password change, `SameSite=Lax`, session key rotation
- [x] Frontend + nginx headers (Frontend repo)
- [x] Review loop until zero findings (3 rounds: 3 + 2 findings fixed, then clean)

### Delivery 3: Identity and invitations (R5, R7)

- [x] Email verification; invitations by email require a verified email (existing users marked verified)
- [x] Uniform, asynchronous password reset
- [x] Review loop until zero findings (3 rounds: 3 + 1 findings fixed, then clean)

### Delivery 4: Operational hardening (R10, R14–R17)

- [x] API docs/admin restrictions, HSTS, dependency scanning, security logging, infra guidance
- [x] Extra: `NUM_PROXIES`, refresh revocation on password reset, plain-string error payloads
- [ ] Review loop until zero findings

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-10-07 | Plan created; Delivery 1 implemented |
| 2026-10-07 | Delivery 1 released after 4 review rounds (PR #24 + Frontend #25) |
| 2026-10-07 | Delivery 2 API implemented (cookie transport); 1265 tests pass |
| 2026-10-07 | Delivery 2 released after 3 review rounds (API #26, Frontend #26, root #4); end-to-end browser check found and fixed signup body tokens |
| 2026-10-07 | Delivery 3 API implemented (email verification, uniform password reset) |
| 2026-10-08 | Delivery 3 released after 3 review rounds (API #27, Frontend #27, root #5); end-to-end check: banner, link, invitation visible after verification, link reuse rejected |
| 2026-10-08 | Delivery 4 implemented (spec `specs/security-hardening-operational.md`); 1312 tests pass |

---

## Decisions

| Decision | Rationale | Alternatives considered |
|----------|-----------|------------------------|
| Signature sniffing in Python | Small allowlist, no native dependency | `python-magic` |
| Raster images are the only inline types | SVG/HTML can run script on the API origin | Inline by `download` flag |
| `StoredFile.save()` recomputes the type from the bytes when the file changes | The stored type must match the content | Recompute on every save |
| Cookie transport opt-in via `X-Auth-Transport: cookie` | Keeps Bearer clients unchanged | Separate browser-only endpoints |
| Invalid access cookie → anonymous | Public endpoints (login) keep working with a stale cookie | 401 on any invalid cookie |
| API docs: public only with `DEBUG`/`API_DOCS_PUBLIC`, else staff | Developers keep docs locally; production hides the API map | Remove docs in production |
| HSTS preload opt-in | Preload is hard to undo; needs an explicit decision | Keep `preload` on |
| Security events logged without emails | Ids + IP are enough to investigate; emails are personal data | Log the attempted email |

---

## Done Criteria

- [ ] All four deliveries merged
- [ ] Tests pass (`make l_test`)
- [ ] Lint passes (`make l_format_code`)
- [ ] Schema regenerated if API changed (`make l_spectacular`)
- [ ] `docs/frontend-integration-guide.md` updated if request/response changed
