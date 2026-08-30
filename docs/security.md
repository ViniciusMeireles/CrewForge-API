# Security

This document defines CrewForge's security invariants, authentication flow,
cookie configuration, and threat model. Agents must follow these rules without
exception.

---

## Table of Contents

- [Authentication Flow](#authentication-flow)
- [Cookie Configuration](#cookie-configuration)
- [Security Invariants](#security-invariants)
- [Password Handling](#password-handling)
- [Token Management](#token-management)
- [Endpoint Security Model](#endpoint-security-model)
- [Secrets Management](#secrets-management)

---

## Authentication Flow

User login is a **3-step process**:

1. **Authenticate the user:**
   ```
   POST /api/auth/token/
   Body: { "email": "...", "password": "..." }
   Response: { "access": "...", "refresh": "...", "user": {...} }
   ```

2. **List available organizations:**
   ```
   GET /api/accounts/organizations/
   Headers: Authorization: Bearer <access>
   Response: { "results": [{ "id": 1, "name": "...", ... }] }
   ```

3. **Set organization context:**
   ```
   POST /api/accounts/organizations/{id}/login/
   Headers: Authorization: Bearer <access>
   Response: { "user": {...}, "organization": {...}, "member": {...} }
   ```

**Critical:** Step 1 authenticates the user but does NOT establish the
organization context. Agents must not assume that obtaining a JWT alone
represents a fully logged-in user.

---

## Cookie Configuration

The organization context relies on the session cookie being sent from the SPA
to the API. This requires explicit CORS and SameSite configuration.

### Production Defaults (`config/settings/base.py`)

```python
CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SECURE = True
```

### Local Development (`config/settings/local.py`)

```python
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
```

### Configuration Matrix

| Scenario | `SameSite` | Extra config |
|---|---|---|
| Same domain (`app.com/api`) | `Lax` or `None` | none |
| Subdomains (`app.com` + `api.app.com`) | `Lax` | `SESSION_COOKIE_DOMAIN=.app.com` |
| Different domains (`app.com` + `api.com`) | `None` | `CSRF_TRUSTED_ORIGINS=https://app.com` |

### Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins | — |
| `SESSION_COOKIE_SAMESITE` | `Lax` or `None` | `None` |
| `CSRF_COOKIE_SAMESITE` | `Lax` or `None` | `None` |
| `SESSION_COOKIE_DOMAIN` | Shared cookie domain | — |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated CSRF origins | — |

**Rule:** `SameSite=None` requires `Secure=True` (HTTPS). Local dev (HTTP)
must use `SameSite=Lax` + `Secure=False` or the browser silently drops the
session cookie.

---

## Security Invariants

These rules are non-negotiable:

1. **Never commit secrets.** Use environment variables via `.env`.
2. **`SECRET_KEY`** must be set via `DJANGO_SECRET_KEY` env var. The fallback
   in `base.py` is a development placeholder only.
3. **`ALLOWED_HOSTS`** must be restricted in production.
4. **`CSRF_COOKIE_SECURE`** and **`SESSION_COOKIE_SECURE`** are `True` by
   default. Only `local.py` relaxes these.
5. **Never log or return** passwords, tokens, or secrets in API responses.
6. **Passwords are always `write_only`** in serializers and handled via
   `set_password()`.
7. **Permission changes** are high-impact: always add tests and review carefully.
8. **Never put real secrets** in `example.env`. Use placeholder values only.

---

## Password Handling

- Passwords are never serialized in read operations (`write_only=True`).
- Passwords are set via `user.set_password()` (Django's hashing).
- Password reset uses a 2-step flow:
  1. `POST /api/auth/password/reset/` — sends email with `uid` + `token`
  2. `POST /api/auth/password/reset/confirm/` — with `uid`, `token`, `new_password`
- Password validation follows Django's `AUTH_PASSWORD_VALIDATORS`.

---

## Token Management

- JWT access tokens are used for API authentication.
- Refresh tokens are rotated on every refresh (`ROTATE_REFRESH_TOKENS=True`).
- Old refresh tokens are blacklisted after rotation.
- Logout blacklists the current refresh token and flushes the session.
- Token obtain endpoint: `POST /api/auth/token/`
- Token refresh endpoint: `POST /api/auth/token/refresh/`
- Token verify endpoint: `POST /api/auth/token/verify/`

---

## Endpoint Security Model

### Authentication Levels

| Level | Description | Example |
|---|---|---|
| `AllowAny` | No authentication required | Signup, Swagger UI |
| `IsAuthenticated` | JWT required, no org context | Token endpoints |
| `IsActiveMember` | JWT + active member in session | Most list endpoints |
| `OrganizationScopedPermission` | JWT + active member + org match | Object-level access |

### Role-Based Access

| Action | Owner | Admin | Manager | Member |
|---|---|---|---|---|
| Read org resources | ✅ | ✅ | ✅ | ✅ |
| Create resources | ✅ | ✅ | ✅ | ✅ |
| Update own record | ✅ | ✅ | ✅ | ✅ |
| Update any member | ✅ | ✅ | ❌ | ❌ |
| Delete members | ✅ | ✅ | ❌ | ❌ |
| Manage invitations | ✅ | ✅ | ❌ | ❌ |
| Manage teams | ✅ | ✅ | ✅ | ❌ |
| Modify org settings | ✅ | ❌ | ❌ | ❌ |

### Cross-Org Isolation

Accessing another organization's resources returns **404** (not 403) because
`OrganizationScopedViewSetMixin` filters the queryset before the view executes.
This prevents resource enumeration.

### Diagnostics Endpoint

`GET /api/accounts/session/config/` is a public endpoint that returns current
cookie and CORS settings. Useful for frontend teams to verify connectivity
before authentication.

---

## Secrets Management

| Secret | Storage | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | `.env` file | Never commit real value |
| `POSTGRES_PASSWORD` | `.env` file | Docker compose reads from `.env` |
| `SENTRY_DSN` | `.env` file | Empty = disabled |
| `FROM_MAIL` | `.env` file | Email sender address |
| `SELF_URL` | `.env` file | Required for file download URLs |
| `FRONTEND_URL` | `.env` file | Required for invitation links |

**Rule:** `example.env` must contain only placeholder values. Real secrets
must never appear in committed files.
