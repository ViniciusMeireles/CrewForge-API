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
- [Security Logging](#security-logging)
- [Production Infrastructure](#production-infrastructure)
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
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = True
AUTH_COOKIE_ACCESS_NAME = '__Host-access'
AUTH_COOKIE_REFRESH_NAME = '__Secure-refresh'
AUTH_COOKIE_SECURE = True
AUTH_COOKIE_SAMESITE = 'Lax'
```

### Local Development (`config/settings/local.py`)

```python
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
AUTH_COOKIE_ACCESS_NAME = 'access'
AUTH_COOKIE_REFRESH_NAME = 'refresh'
AUTH_COOKIE_SECURE = False
CSRF_TRUSTED_ORIGINS = ['http://localhost:4200', 'http://127.0.0.1:4200']
```

The `__Host-`/`__Secure-` prefixes require HTTPS, so development uses plain
names.

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
| `SESSION_COOKIE_SAMESITE` | `Lax` or `None` | `Lax` |
| `CSRF_COOKIE_SAMESITE` | `Lax` or `None` | `Lax` |
| `SESSION_COOKIE_DOMAIN` | Shared cookie domain | — |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated CSRF origins | — |

**Rule:** `SameSite=None` requires `Secure=True` (HTTPS). Local dev (HTTP)
must use `SameSite=Lax` + `Secure=False` or the browser silently drops the
session cookie.

---

## Security Invariants

These rules are non-negotiable:

1. **Never commit secrets.** Use environment variables via `.env`.
2. **`SECRET_KEY`** must be set via `DJANGO_SECRET_KEY` env var. There is no
   fallback outside development: `production.py` — and `local.py` when
   `ENVIRONMENT` is not `local_development`/`devcontainer`/`test` — refuse to
   start without a key of at least 50 characters (`config/settings/checks.py`).
   `run.sh` exports `ENVIRONMENT=production` by default.
   JWTs are signed with `JWT_SIGNING_KEY` when set (same rules), else with the
   secret key.
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
- The reset request answers the same message whether or not the email exists
  (no user enumeration); the email is sent asynchronously.

## Email Verification

- `User.email_verified_at` records when the user proved access to the email.
  Signup users start unverified and get a link
  (`apps/accounts/utils/email_verification.py`; token hash includes the email
  and the verification date, so links die after use or email change).
  Invitation-link signups are verified on creation; changing the email resets it.
- Verification emails are limited to one per user every 5 minutes
  (`EMAIL_VERIFICATION_COOLDOWN_SECONDS`, `User.email_verification_sent_at`), so
  resend and email changes cannot be used to spam inboxes.
- Stored file responses expose the owner as id/username/name only (no email).
- Invitations are matched by email **only for verified users**
  (`filter_received_by_user`, `InvitationAcceptDeclinePermission`), so
  registering someone else's address does not expose or accept their
  invitations.

---

## Token Management

- JWT access tokens are used for API authentication.
- Browsers use **HttpOnly cookies** (`JWTCookieAuthentication`,
  `apps/accounts/authentication.py`): an `Authorization` header wins; otherwise
  the access cookie authenticates and Django CSRF is enforced for unsafe
  methods. Cookie mode (`X-Auth-Transport: cookie`, or a request authenticated
  by cookie) never returns tokens in response bodies; a refresh read from the
  cookie never does either. Cookies: `__Host-access` (path `/`) and
  `__Secure-refresh` (path `/api/auth/`), HttpOnly, Secure, `SameSite=Lax`.
- Access tokens live 15 minutes by default (`ACCESS_TOKEN_LIFETIME`).
- Behind a TLS-terminating proxy, cookie-mode CSRF needs Django to see HTTPS:
  set `SECURE_PROXY_SSL_HEADER=True` and forward the original
  `X-Forwarded-Proto`, or set `CSRF_TRUSTED_ORIGINS` to the public origin.
- Changing or resetting the password blacklists every outstanding refresh
  token of the user (`apps/accounts/utils/tokens.py`).
- Organization login rotates the session key (`cycle_key`) to prevent session
  fixation.
- Login, signup and password reset use the `auth` throttle scope; refresh uses
  `auth_refresh`.
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

### Default Permission

`DEFAULT_PERMISSION_CLASSES` is `IsAuthenticated`: a view without explicit
`permission_classes` is closed. Public endpoints must declare `AllowAny`, and
`apps/generics/tests/test_default_permissions.py` pins the list of public
routes — adding one requires updating that allowlist on purpose.

### Diagnostics Endpoint

`GET /api/accounts/session/config/` is public and sets the CSRF cookie. It only
returns cookie, CORS and debug diagnostics when `DEBUG=True`.

### API Docs and Admin

- `/api/schema/`, `/api/schema/swagger-ui/` and `/api/schema/redoc/` use
  `ApiDocsPermission` (`apps/generics/permissions.py`): public when
  `API_DOCS_PUBLIC=True`, or when it is unset and `DEBUG=True`; otherwise only
  staff users (Django admin session or JWT) can read them.
- The Django admin is served at `ADMIN_URL` (default `admin/`). The Frontend
  nginx only forwards `/api/`, so the admin is not reachable through the public
  proxy; expose it only on an internal network or VPN.

### Stored Files

- Uploads are limited by `STORED_FILE_MAX_SIZE`: `UploadSizeLimitMixin` rejects
  an oversized `Content-Length` after authentication and before parsing, and
  `MaxSizeUploadHandler` (first in `FILE_UPLOAD_HANDLERS`, so it also covers
  the admin) stops storing a file as soon as it passes the limit; the
  serializers then report it as too large (`UploadTooLargeMixin`). The type is detected from the file bytes
  (`apps/accounts/utils/files.py`); the extension must match.
- `StoredFile.save()` recomputes `content_type` from the bytes whenever the file
  is replaced, so the stored type never goes stale.
  Allowed types: `STORED_FILE_ALLOWED_CONTENT_TYPES`; organization images only
  accept `STORED_FILE_IMAGE_CONTENT_TYPES` (raster images).
- Downloads are attachments unless the type is in
  `STORED_FILE_INLINE_CONTENT_TYPES` (raster images). Every file response sets
  `X-Content-Type-Options: nosniff` and `Content-Security-Policy: sandbox;
  default-src 'none'`, so an uploaded file can never run script on the API
  origin.

---

## Security Logging

Authentication events go to the `security` logger
(`apps/accounts/utils/security_log.py`), one line per event in `key=value`
form, also attached to the record as `security_event` for structured handlers.
Records carry the event, `user_id` (when known), the client `ip` and
event-specific ids — never emails, passwords or tokens.

| Event | Level |
|---|---|
| `auth.login.succeeded` / `auth.login.failed` | INFO / WARNING |
| `auth.throttled` (with `scope`) | WARNING |
| `auth.refresh.rejected` | WARNING |
| `auth.logout`, `auth.signup` | INFO |
| `auth.password.changed` / `auth.password_change.failed` | INFO / WARNING |
| `auth.password_reset.requested` / `.completed` / `.failed` | INFO / INFO / WARNING |
| `auth.email.verified` / `auth.email_verification.failed` | INFO / WARNING |
| `organization.login`, `invitation.accepted` | INFO |

The level is set by `SECURITY_LOG_LEVEL` (default `INFO`); the handler writes to
stderr, so the container logs collect it.

The client IP is resolved like the throttles (DRF `get_ident`): set
`NUM_PROXIES` to the number of trusted proxies in front of the API (1 behind
the Frontend nginx). Without it, a client-supplied `X-Forwarded-For` is
trusted, which lets a client dodge the `auth` throttle and fake its logged IP.

---

## Production Infrastructure

The `docker-compose.yml` of this repository is for development only: it
mounts the source code, runs `runserver`, starts Mailpit and publishes ports
on `127.0.0.1`. A production deployment must:

- Expose only the Frontend nginx (HTTPS at the edge). PostgreSQL, Redis,
  Flower and the API port stay on a private network with no published ports.
- Run with `DJANGO_SETTINGS_MODULE=config.settings.production`,
  `ENVIRONMENT=production`, a 50+ character `DJANGO_SECRET_KEY`, a restricted
  `ALLOWED_HOSTS`, `SECURE_PROXY_SSL_HEADER=True` and `NUM_PROXIES` matching
  the proxy chain (`production.py` refuses to start without `NUM_PROXIES`).
- Keep HSTS at one year (`SECURE_HSTS_SECONDS=31536000`, the default) once
  HTTPS works on every subdomain; enable `SECURE_HSTS_PRELOAD` only after
  deciding to submit the domain to the preload list.
- Protect Flower with `FLOWER_BASIC_AUTH` (the compose refuses to start it
  without one) and keep it internal.
- Use strong, unique credentials for PostgreSQL, Redis and SMTP.

Dependencies are checked by Dependabot (`.github/dependabot.yml`: uv, GitHub
Actions, Docker) and by `pip-audit` in CI, which fails the build on a known
vulnerability.

---

## Secrets Management

| Secret | Storage | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | `.env` file | Never commit real value; required (50+ chars) outside local/test |
| `JWT_SIGNING_KEY` | `.env` file | Optional; signs JWTs (50+ chars) |
| `POSTGRES_PASSWORD` | `.env` file | Docker compose reads from `.env` |
| `FLOWER_BASIC_AUTH` | `.env` file | `user:password` for Flower; required to start it |
| `SENTRY_DSN` | `.env` file | Empty = disabled |
| `FROM_MAIL` | `.env` file | Email sender address |
| `SELF_URL` | `.env` file | Required for file download URLs |
| `FRONTEND_URL` | `.env` file | Required for invitation links |

**Rule:** `example.env` must contain only placeholder values. Real secrets
must never appear in committed files.
