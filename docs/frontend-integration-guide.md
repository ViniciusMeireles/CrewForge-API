# Frontend Integration Guide

## Table of Contents

- [Overview](#1-overview)
- [Getting Started](#2-getting-started)
- [Authentication Flow](#3-authentication-flow)
- [Password Reset](#4-password-reset)
- [Signup](#5-signup)
- [User Profile](#6-user-profile)
- [Organization Management](#7-organization-management)
- [Member Management](#8-member-management)
- [Invitations](#9-invitations)
- [Teams](#10-teams)
- [Team Members](#11-team-members)
- [File Upload & Download](#12-file-upload--download)
- [Error Handling](#13-error-handling)
- [Pagination](#14-pagination)
- [Form Options Endpoints](#15-form-options-endpoints)
- [Dashboard](#16-dashboard)
- [Audit Trail](#17-audit-trail)
- [Platform Panel](#18-platform-panel)
- [Troubleshooting](#19-troubleshooting)

---

## 1. Overview

CrewForge is a Django REST API that uses a **two-layer authentication model**:

1. **JWT tokens** for API authentication. Browsers receive them as **HttpOnly cookies** (see [3.9](#39-browser-sessions-httponly-cookies)); other clients use `Authorization: Bearer <access>`.
2. **Django session cookie** (`sessionid`) for organization context.

All endpoints are prefixed with `/api/`.

The API is organized into four main namespaces:

| Prefix | Purpose |
|---|---|
| `/api/auth/` | Authentication, token refresh, password reset |
| `/api/accounts/` | Organizations, members, invitations, files, user profile, signup |
| `/api/teams/` | Teams and team memberships |
| `/api/dashboard/` | Organization overview for the dashboard page |

---

## 2. Getting Started

### 2.1. Environment Checklist

Required variables in `.env` for frontend integration:

| Variable | Example value | Purpose |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | `http://localhost:4200` | Browser CORS policy |
| `FRONTEND_URL` | `http://localhost:4200` | Base URL for invitation accept links |
| `FRONTEND_RESET_URL` | `http://localhost:4200/auth/reset-password` | Base URL for password reset links |
| `SELF_URL` | `http://localhost:8000` | Absolute file download URLs |

### 2.2. API Base URL

All requests target a single base URL. Example for local development:

```
http://localhost:8000/api/
```

### 2.3. CORS & Cookie Configuration

Cookie settings differ between development and production:

| Setting | Development (HTTP) | Production (HTTPS) |
|---|---|---|
| `SESSION_COOKIE_SAMESITE` / `CSRF_COOKIE_SAMESITE` | `Lax` | `Lax` (default; `None` only for cross-site setups) |
| `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` | `False` | `True` |
| Access / refresh cookie names | `access` / `refresh` | `__Host-access` / `__Secure-refresh` |
| `AUTH_COOKIE_SECURE` | `False` | `True` |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:4200,http://127.0.0.1:4200` | — (same origin behind the proxy) |

> **Warning:** `SameSite=None` + `Secure=False` is invalid. Modern browsers silently reject such cookies. Development must use `Lax` because HTTP cannot set Secure cookies.

The public endpoint `GET /api/accounts/session/config/` returns `session_configured` and sets the `csrftoken` cookie. When the API runs with `DEBUG=True` it also returns the cookie and CORS settings (`cookie_settings`, `cors_allowed_origins`, `cors_allow_credentials`, `debug`) for debugging connectivity; in production these diagnostics are omitted.

---

## 3. Authentication Flow

### 3.1. Overview (3-Step Flow)

```
Step 1: POST /api/auth/token/           → JWT tokens + user data
Step 2: GET  /api/accounts/organizations/ → list user's organizations
Step 3: POST /api/accounts/organizations/{id}/login/ → session cookie
```

**Important:** Step 1 authenticates the user but does **not** establish the organization context. Most organization-scoped endpoints require all three steps.

### 3.2. Step 1 — Token Obtain

**Request:**
```
POST /api/auth/token/
Content-Type: application/json

{
  "username": "john",
  "password": "secret123"
}
```

**Response (200):**
```json
{
  "refresh": "eyJhbGciOiJI...",
  "access": "eyJhbGciOiJI..."
}
```

This body shape is for **non-browser (Bearer) clients**: store both tokens and send `Authorization: Bearer <access>`.

> **Browsers (SPA) must not do this.** Send `X-Auth-Transport: cookie` (and `X-CSRFToken`): the tokens arrive as HttpOnly cookies and the body only has `auth_user`. Never keep tokens in `localStorage`/`sessionStorage`. See [3.9](#39-browser-sessions-httponly-cookies).

### 3.3. Step 2 — List Organizations

**Request:**
```
GET /api/accounts/organizations/
Authorization: Bearer eyJhbGciOiJI...
```

**Response (200) — paginated:**
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Acme Corp",
      "slug": "acme-corp",
      "profile": {
        "id": 1,
        "website": "https://acme.example.com",
        "description": "A company"
      }
    }
  ]
}
```

Parse the results and present the list so the user can pick an organization.

The list requires authentication (anonymous → 401) and only returns active
Organizations where the user has an active Member (suspended ones included, so
the selection screen can show their state). Retrieving another Organization
returns 404.

#### 3.3.1. Filtering Organizations

The list endpoint supports the following query parameters:

| Parameter | Type | Description |
|---|---|---|
| `my_organizations` | `boolean` | Accepted for compatibility; has no effect, the list is always restricted to the user's Organizations |
| `name` | `string` | Exact match on name |
| `name__icontains` | `string` | Case-insensitive name contains |
| `slug` | `string` | Exact match on slug |
| `slug__icontains` | `string` | Case-insensitive slug contains |
| `is_active` | `boolean` | Filter by active status |

**Example — search the user's organizations by name:**

```
GET /api/accounts/organizations/?name__icontains=acme
```

### 3.4. Step 3 — Organization Login

**Request:**
```
POST /api/accounts/organizations/1/login/
Authorization: Bearer eyJhbGciOiJI...
```

**No request body.** The frontend must send `withCredentials: true` (or `credentials: 'include'`) so the browser accepts the `sessionid` cookie.

**Response (200):**
```json
{
  "user": {
    "id": 1,
    "username": "john",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "organizations": [
    {
      "id": 1,
      "name": "Acme Corp",
      "slug": "acme-corp",
      "profile": null
    }
  ],
  "organization": {
    "id": 1,
    "name": "Acme Corp",
    "slug": "acme-corp",
    "profile": null
  },
  "member": {
    "id": 1,
    "role": "OWNER",
    "nickname": null,
    "permissions": {
      "is_owner": true,
      "is_admin": false,
      "is_manager": false,
      "is_member": false,
      "has_owner_permission": true,
      "has_admin_permission": true,
      "has_manager_permission": true,
      "has_member_permission": true
    },
    "access": {
      "members": true,
      "invitations": true,
      "teams": true,
      "organization_settings": true
    },
    "last_login_at": "2026-07-10T12:00:00Z"
  }
}
```

### 3.5. After Authentication

All subsequent requests need the user authentication **and** the organization session cookie:

| Client | User authentication | Organization context |
|---|---|---|
| Browser (SPA) | access cookie (HttpOnly, sent automatically) + `X-CSRFToken` on unsafe methods | `sessionid` cookie (automatic) |
| Bearer client | `Authorization: Bearer <access>` | `sessionid` cookie (keep the cookie jar) |

### 3.6. Session State

Use this endpoint to restore the application state after a page refresh:

```
GET /api/accounts/session/
```

Returns the same shape as the login response (user, organizations, organization, member). If the user is authenticated but has no active organization, `organization` and `member` are `null`.

#### Member access (`member.access`)

`member.access` tells which management areas the member can open. Use it to build the menu and route guards — do **not** derive area access from `role` or `permissions`.

| Key | Area | Granted to |
|-----|------|------------|
| `members` | Members screen | Any active member |
| `invitations` | Invitations screen | Members with OWNER or ADMIN role |
| `teams` | Teams screen | Any active member |
| `organization_settings` | Organization settings screen | Members with OWNER role |
| `audit` | Audit screen | Members with OWNER or ADMIN role |

Keys follow the Member's Role only: `is_superuser` grants nothing inside an Organization (ADR-009). `access` is computed on every request (never cached server-side), so re-read the session after a `403` or after a role change to get fresh values. Action-level checks inside a screen (e.g., showing an "Invite" button) still use `member.permissions`.

### 3.7. Token Refresh

**Request:**
```
POST /api/auth/token/refresh/
Content-Type: application/json

{
  "refresh": "eyJhbGciOiJI..."
}
```

**Response (200):**
```json
{
  "access": "eyJhbGciOiJI...",
  "refresh": "eyJhbGciOiJI..."
}
```

Because `ROTATE_REFRESH_TOKENS=True`, every refresh returns a **new** refresh token. The old one is blacklisted. The frontend must store the new refresh token after each refresh.

**Recommended flow:** Create an HTTP interceptor that catches 401 responses, attempts a token refresh, stores the new tokens, then retries the original request. If the refresh also fails, redirect to login.

### 3.8. Logout

**Request:**
```
POST /api/auth/logout/
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJI...

{
  "refresh": "eyJhbGciOiJI..."
}
```

**Response (200):** `{"detail": "Logout successful."}`

The server blacklists the refresh token and flushes the session. The frontend should discard stored tokens and clear any cached state.

### 3.9. Browser Sessions (HttpOnly Cookies)

Browsers must never handle tokens in JavaScript. Send `X-Auth-Transport: cookie` on every same-origin API request and the API moves the tokens into cookies:

| Cookie | Flags | Path | Lifetime |
|---|---|---|---|
| access (`__Host-access`; `access` in development) | HttpOnly, Secure (prod), `SameSite=Lax` | `/` | `ACCESS_TOKEN_LIFETIME` (15 min) |
| refresh (`__Secure-refresh`; `refresh` in development) | HttpOnly, Secure (prod), `SameSite=Lax` | `/api/auth/` | `REFRESH_TOKEN_LIFETIME` (7 days) |
| `csrftoken` (readable by JS) | Secure (prod), `SameSite=Lax` | `/` | Django default |

Rules:

- **CSRF:** every unsafe request authenticated by the access cookie, and every cookie-mode login/signup/refresh/logout, needs `X-CSRFToken: <csrftoken cookie>`. Get the `csrftoken` cookie from `GET /api/accounts/session/config/` before the first `POST`. Bearer requests do not need CSRF.
- **HTTPS behind a proxy:** Django's CSRF check compares the browser `Origin` with the scheme it sees. When TLS terminates in a proxy, set `SECURE_PROXY_SSL_HEADER=True` and make every proxy forward the original `X-Forwarded-Proto: https` (the Frontend nginx forwards the incoming header), or list the public origin in `CSRF_TRUSTED_ORIGINS`. Otherwise every cookie-mode `POST` fails with 403 "Origin checking failed".
- **Issuers** (`/auth/token/`, signup, `create-with-invite`, invitation `accept`, change password): in cookie mode the response sets both cookies and **omits** `access`/`refresh` (and `user.auth_token`) from the body.
- **Refresh:** `POST /api/auth/token/refresh/` with an empty body uses the refresh cookie, rotates it and answers `{}` plus new cookies — never tokens in the body. An invalid/expired refresh cookie answers 401 and clears both cookies.
- **Logout:** `POST /api/auth/logout/` without body blacklists the refresh cookie, clears both cookies and flushes the session (204).
- **Restoring the session on page load:** call `GET /api/accounts/session/`; on 401 call the refresh endpoint once and retry. Do not read tokens from storage.
- An invalid or expired access cookie is ignored (the request is anonymous), so public endpoints such as login keep working.
- Login, signup and password reset are rate limited (`AUTH_THROTTLE_RATE`, default `10/min`); refresh has its own limit (`AUTH_REFRESH_THROTTLE_RATE`, default `60/min`). Throttled requests get 429.

---

## 4. Password Reset

### 4.1. Request Reset

**Request:**
```
POST /api/auth/password/reset/
Content-Type: application/json

{
  "email": "john@example.com"
}
```

**Response (200):** `{"detail": "If an account exists for this email, a password reset link has been sent to it. Please check your inbox."}`

The response is **identical whether the email exists or not** (no user enumeration), and the email is sent asynchronously. The email contains a link with `uid` and `token` query parameters.

### 4.2. Confirm Reset

The frontend extracts `uid` and `token` from the reset URL query parameters (configured via `FRONTEND_RESET_URL`).

**Request:**
```
POST /api/auth/password/reset/confirm/
Content-Type: application/json

{
  "uid": "MQ",
  "token": "b3xr9d-...",
  "new_password": "new-secret-123"
}
```

**Response (200):** `{"detail": "Password has been reset successfully."}`

### 4.3. Email Verification

Users created by signup start **unverified** and receive an email with a link to `FRONTEND_VERIFY_EMAIL_URL?uid=...&token=...` (default `FRONTEND_URL/auth/verify-email`). Users created through an invitation link (`create-with-invite`) are verified on creation, because the link proves access to the mailbox. Changing the email in the profile makes the user unverified again and sends a new link.

| Action | Endpoint | Auth |
|---|---|---|
| Confirm | `POST /api/auth/email/verify/` with `{"uid", "token"}` → 200 / 400 (`Invalid verification link.`) | Public |
| Resend link | `POST /api/auth/email/verify/resend/` → 200 (no email if already verified), 429 with `retry_after_seconds` during the cooldown | Authenticated |

At most one link is sent per user every 5 minutes (`EMAIL_VERIFICATION_COOLDOWN_SECONDS`); an email change inside the cooldown updates the email without sending, and the user can resend afterwards. Links expire after `PASSWORD_RESET_TIMEOUT` and stop working once used or when the email changes. `user.email_verified` is returned in the session (`user`), token obtain (`auth_user`) and profile responses.

The email renders in the recipient's profile `preferred_language` (see [6.2](#62-update-profile)), not in the language of the request that triggered the send.

**Unverified users do not see or accept invitations addressed to their email** (received list is empty, accept/decline → 403). Opening an invitation link by key still works.

---

## 5. Signup

Creates a user and organization simultaneously. The user becomes the organization owner.

**Request:**
```
POST /api/accounts/signup/
Content-Type: application/json

{
  "user": {
    "username": "john",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "password": "secure-pass-123"
  },
  "organization": {
    "name": "My Organization",
    "profile": {
      "website": "https://example.com",
      "description": "Optional description"
    }
  }
}
```

**Response (201):**
```json
{
  "id": 1,
  "user": {
    "id": 1,
    "username": "john",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "auth_token": {
      "refresh": "eyJhbGciOiJI...",
      "access": "eyJhbGciOiJI..."
    }
  },
  "organization": {
    "id": 1,
    "name": "My Organization",
    "slug": "my-organization",
    "profile": {
      "id": 1,
      "website": "https://example.com",
      "description": "Optional description"
    }
  },
  "is_active": true,
  "created_at": "2026-07-10T12:00:00Z",
  "updated_at": "2026-07-10T12:00:00Z",
  "created_by": 1,
  "updated_by": 1
}
```

Bearer clients get the JWT tokens in `user.auth_token`. Browsers sending `X-Auth-Transport: cookie` receive them as HttpOnly cookies and `user.auth_token` is omitted (see [3.9](#39-browser-sessions-httponly-cookies)). Then call the organization login (Step 3) to establish the session.

---

## 6. User Profile

### 6.1. Retrieve Current User

```
GET /api/accounts/users/me/
Authorization: Bearer eyJhbGciOiJI...
```

**Response (200):**
```json
{
  "id": 1,
  "username": "john",
  "email": "john@example.com",
  "email_verified": true,
  "first_name": "John",
  "last_name": "Doe",
  "preferred_language": "en"
}
```

No organization context required (uses `IsAuthenticated` only).

### 6.2. Update Profile

```
PATCH /api/accounts/users/me/
Authorization: Bearer eyJhbGciOiJI...
Content-Type: application/json

{
  "first_name": "Jonathan",
  "last_name": "Smith",
  "email": "jonathan@example.com",
  "preferred_language": "pt-br"
}
```

`username` and `id` are read-only. Partial updates are supported.

`preferred_language` accepts exactly `en` or `pt-br` (lower-case); anything else is a 400 validation error. It decides the language of the user's emails (verification, password reset, invitations addressed to them). It is profile-only: it is never exposed on nested user payloads and cannot be set through member or invitation flows. It is initialized at creation from the `Accept-Language` of the signup / create-with-invite request (`pt*` → `pt-br`, anything else → `en`); the user changes it here afterwards.

### 6.3. Change Password

```
POST /api/accounts/users/me/change-password/
Authorization: Bearer eyJhbGciOiJI...
Content-Type: application/json

{
  "current_password": "old-pass-123",
  "new_password": "new-pass-456"
}
```

**Response (200):** `{"detail": "Password changed successfully."}`

Validates that the new password differs from the current one and passes the password validators (at least 8 characters, not common, not numeric-only, not similar to the user's data); errors come on `new_password`. Signup, signup by invitation and password reset confirm apply the same validators (errors on `user.password` / `password` / `new_password`), and the signup password is required.

Changing the password **revokes every session** of the user: access tokens issued before it stop working at once and every refresh token is blacklisted. In cookie mode the response sets a fresh pair of cookies so the current browser stays logged in; Bearer clients must log in again. A password reset revokes every session too.

---

## 7. Organization Management

| Action | Endpoint | Permission |
|---|---|---|
| List | `GET /api/accounts/organizations/` | Authenticated user (member of) |
| Create | `POST /api/accounts/organizations/` | Any authenticated user |
| Retrieve | `GET /api/accounts/organizations/{id}/` | Member of the organization |
| Update | `PUT/PATCH /api/accounts/organizations/{id}/` | Owner of the organization (in its session) |
| Delete | `DELETE /api/accounts/organizations/{id}/` | Owner of the organization (in its session) |
| Login | `POST /api/accounts/organizations/{id}/login/` | Active member |
| Filter options | `GET /api/accounts/organizations/filter-options/` | Same as List |

---

## 8. Member Management

| Action | Endpoint | Permission |
|---|---|---|
| List | `GET /api/accounts/members/` | Member of the org |
| Retrieve | `GET /api/accounts/members/{id}/` | Member of the org |
| Update | `PUT/PATCH /api/accounts/members/{id}/` (`role` and the nested `user` are read-only here; users edit their own profile at `/api/accounts/users/me/`) | Yourself, or admin+ (owner to edit an owner) |
| Update role | `PATCH /api/accounts/members/{id}/update-role/` | Admin+; never your own role (400); new role must be assignable; the Owner's role never changes here (403) |
| Delete | `DELETE /api/accounts/members/{id}/` | Yourself (leave), or admin+; the Owner is never deleted, not even by itself (403, message: transfer ownership first) |
| Create via invite | `POST /api/accounts/members/create-with-invite/{invitation_key}/` | No auth required |
| Filter options | `GET /api/accounts/members/filter-options/` | Same as List (every role listed) |
| Update-role options | `GET /api/accounts/members/form-options-update-role/` | Member of the org (only roles the caller may assign) |

### 8.1. Create Member via Invitation

This endpoint is unauthenticated (intended for the invitee). The invitation's key is a UUID.

**Request:**
```
POST /api/accounts/members/create-with-invite/{invitation_key}/
Content-Type: application/json
No auth headers

{
  "user": {
    "username": "jane",
    "first_name": "Jane",
    "last_name": "Doe",
    "password": "secure-pass-456"
  }
}
```

Email and role are taken from the invitation itself (not from the request body).

**Response (200):** Same shape as signup: nested `user` plus membership fields. Bearer clients get the tokens in `user.auth_token`; in cookie mode they are set as cookies and omitted from the body.

### 8.2. Join Date and Removal

- Member responses include a read-only `joined_at`: when the **current** membership started (creation, or readmission — see [9](#9-invitations)). Prefer it over `created_at`, which is when the row was first created.
- Removing a member (`DELETE /api/accounts/members/{id}/`, soft-delete) also ends all of their team memberships, so a readmitted member starts without teams.

---

## 9. Invitations

| Action | Endpoint | Permission |
|---|---|---|
| List | `GET /api/accounts/invitations/` | Admins see MANAGER+MEMBER; owners see all roles |
| Create | `POST /api/accounts/invitations/` | Admin+ (owner for the ADMIN role; OWNER cannot be invited) |
| Retrieve | `GET /api/accounts/invitations/{id}/` | Owner: any role; Admin: MANAGER+MEMBER only |
| Update | `PUT /api/accounts/invitations/{id}/` | Owner: any role; Admin: MANAGER+MEMBER only |
| Delete | `DELETE /api/accounts/invitations/{id}/` | Owner: any role; Admin: MANAGER+MEMBER only |
| Send email | `POST /api/accounts/invitations/{id}/send-email/` | Owner: any role; Admin: MANAGER+MEMBER only |
| Form options (create) | `GET /api/accounts/invitations/form-options-create/` | Admin+ |
| Form options (update) | `GET /api/accounts/invitations/form-options-update/` | Admin+ |
| Filter options | `GET /api/accounts/invitations/filter-options/` | Admin+ |
| By key | `GET /api/accounts/invitations/by-key/{invitation_key}/` | Public (invitation link landing) |
| Received list | `GET /api/accounts/invitations/received/` | Authenticated user with a verified email |
| Received detail | `GET /api/accounts/invitations/received/{invitation_pk}/` | Authenticated user with a verified email |
| Received filter options | `GET /api/accounts/invitations/received/filter-options/` | Authenticated user (every role listed) |
| Accept | `POST /api/accounts/invitations/{invitation_pk}/accept/` | The invitee (verified email matching the invitation) |
| Decline | `POST /api/accounts/invitations/{invitation_pk}/decline/` | The invitee (verified email matching the invitation) |

Received invitations (`/api/accounts/invitations/received/`, `accept`, `decline`) match the invitation email only for users with a **verified** email (see [4.3](#43-email-verification)).

**Status.** Every invitation response has a read-only `status`: `pending`, `accepted`, `declined`, `expired` or `revoked` (a pending invitation past `expired_at` already reads `expired`). `is_accepted`, `is_declined` and `is_expired` stay as read-only booleans derived from it, and the list accepts `status=<value>` next to the existing `is_*` filters. Deleting an invitation revokes it (`status: revoked`). One pending invitation exists per organization and email (case-insensitive): a second one answers **400** "An invitation with this email already exists.", also under concurrent requests. The role `owner` cannot be invited nor set through `update-role` (form options list Admin, Manager and Member); ownership moves only through the platform transfer. Two concurrent accepts (or accept and decline) of one invitation leave one outcome: the other request gets **400** with the message of the new state.

Invitations of a deactivated (soft-deleted) organization are not listed as received and cannot be accepted or declined (**400** "The organization is no longer active."). An invitation is pending (acceptable) only while it is active, not accepted, declined or expired, `expired_at` is in the future, and the invitee — the linked user, or the active user with the invitation email — is not an **active** member of the organization (`accept` answers **400** "User is already a member").

**Readmission.** A removed member can be invited again: creating an invitation only rejects the email of an **active** member (**400** on `email`). Organization-side invitation responses (list, retrieve, create, update) include a read-only `is_former_member` — the invitee has a removed membership and no active one — so the UI can flag it. They also include read-only `created_at` and `updated_at` (ISO 8601), which are valid `order_by` values as well. Accepting such an invitation (`POST .../{id}/accept/`) reactivates the old member instead of creating one: role from the invitation, `nickname` from the request (or empty; the old one is dropped), a new `joined_at`, no teams. The response adds `readmitted` (`true` for a readmission, `false` for a new member) next to `member_id`; a `nickname` used by another member of the organization answers **400** on `nickname` ("This nickname is already in use in this organization.") and nothing changes. Readmissions are logged as `member.readmitted`.

Invitation emails render in the invitee's profile `preferred_language` (see [6.2](#62-update-profile)) when the invite address belongs to a user; otherwise they fall back to the language of the request that sent them (`en` by default).

### Send Email Cooldown

`POST /api/accounts/invitations/{id}/send-email/` has a 60-second cooldown:

| Status | Meaning |
|---|---|
| **200** | Email sent successfully |
| **400** | Invitation expired, user already a member, or organization no longer active |
| **404** | Invitation not found |
| **429** | Cooldown active (include `retry_after_seconds` in response) |

Invitations are looked up by primary key (`id`), not by the UUID `key`.

---

## 10. Teams

| Action | Endpoint | Permission |
|---|---|---|
| List | `GET /api/teams/teams/` | Member of the org |
| Create | `POST /api/teams/teams/` | Org manager+ |
| Retrieve | `GET /api/teams/teams/{id}/` | Member of the org |
| Update | `PUT /api/teams/teams/{id}/` (no `PATCH`) | Org manager+ (a team owner/admin role alone does not grant it) |
| Delete | `DELETE /api/teams/teams/{id}/` | Org manager+ (a team owner/admin role alone does not grant it) |
| Filter options | `GET /api/teams/teams/filter-options/` | Same as List |

Creating a team auto-creates a `TeamMember` record with `OWNER` role for the creator.

- `slug` is **read-only**: it is auto-generated from `name` on create and regenerated
  whenever `name` changes. Send `name` only — ignore `slug` in payloads.
- The list response includes `member_count` (active team members); create, retrieve
  and update responses do not.
- `name` and `slug` must be unique per organization **among active teams**. A
  duplicate returns `400` with `name: ["This team already exists."]`. Soft-deleted
  teams release their `name`/`slug` for reuse.

---

## 11. Team Members

| Action | Endpoint | Permission |
|---|---|---|
| List | `GET /api/teams/team-members/` | Member of the org |
| Create | `POST /api/teams/team-members/` | Org manager+ or team owner/admin (role must be assignable) |
| Retrieve | `GET /api/teams/team-members/{id}/` | Member of the org |
| Update role | `PUT /api/teams/team-members/{id}/` (`{"role": ...}`) | Org manager+ or team owner/admin; not your own record; target role and new role assignable |
| Delete | `DELETE /api/teams/team-members/{id}/` | Yourself (leave the team), or org manager+ / team owner/admin with the target role assignable |
| Form options (create) | `GET /api/teams/team-members/form-options-create/?team_id=<id>` | Member of the org |
| Form options (update) | `GET /api/teams/team-members/form-options-update/?team_id=<id>` | Member of the org |
| Filter options | `GET /api/teams/team-members/filter-options/` | Member of the org |

Assignable team roles (per team):

| Caller | Roles |
|---|---|
| Organization manager+ (any team) | `owner`, `admin`, `manager`, `member` |
| Team owner | `owner`, `admin`, `manager`, `member` |
| Team admin | `manager`, `member` |
| Others | none |

- Adding without permission on the team answers **400** on `team`; an unassignable role
  answers **400** on `role`; editing or removing a record you may not touch answers **403**.
- The team must keep at least one active owner: removing or demoting the last owner answers
  **400** on `role` ("The team must keep at least one owner.").
- Re-adding a previously removed (soft-deleted) team member reactivates their membership
  (same permission as adding); without `role` it comes back as `member`, never with the
  old role.
- Responses include `role_label` and a read-only `member_detail` (`id`, `full_name`,
  `email`, `nickname`, `role`, `role_label` of the organization member). `member` stays the
  writable id.
- The list is paginated (10 by default): a drawer listing a whole team should send
  `page_size` (max 100) and request the next `page`.
- Ordering (`?order_by=`, prefix `-` for descending): `member_name`, `member_email`,
  `role` (hierarchy: owner, admin, manager, member), `created_at` (joined at), `id`.
  `filter-options/?order_by` lists them.

---

## 12. File Upload & Download

### 12.1. Upload

```
POST /api/accounts/stored-files/
Authorization: Bearer eyJhbGciOiJI...
Content-Type: multipart/form-data

file: (binary file data)
name: "report.pdf"
viewing_permission: "MEMBER"
updating_permission: "MANAGER"
```

`viewing_permission` and `updating_permission` control access at the org-role level.

**Upload rules** (`400` on the `file` field when violated):

- Maximum size: `STORED_FILE_MAX_SIZE` (default 10 MB). Authenticated requests whose `Content-Length` exceeds it (plus 1 MB for the other form fields) are rejected before the body is read; the error is on `file` (`image.file` for organization images). Proxies in front of the API must allow at least this size (the Frontend nginx sets `client_max_body_size 11m`).
- The type is detected from the file **content**, not the name. Allowed by default (`STORED_FILE_ALLOWED_CONTENT_TYPES`): PNG, JPEG, GIF, WebP, PDF, plain text, CSV and JSON (UTF-8 or Windows-1252), ZIP, Word/Excel/PowerPoint (`.doc`/`.xls`/`.ppt` and `.docx`/`.xlsx`/`.pptx`) and OpenDocument (`.odt`/`.ods`/`.odp`). Organization images accept only PNG, JPEG, GIF and WebP.
- A known extension must match the detected type (`fake.png` containing HTML is rejected). Files without extension take the detected type.
- HTML, SVG, scripts and executables are always rejected.

### 12.2. Download

```
GET /api/accounts/stored-files/{uuid}/file/?download=true
Authorization: Bearer eyJhbGciOiJI...
```

Bearer clients must send the `Authorization` header. Browsers are authenticated by the access cookie; the SPA still fetches via `HttpClient` with `responseType: 'blob'` (e.g. `AuthImage`) so it can handle errors and object URLs.

Only raster images (PNG, JPEG, GIF, WebP) are served inline, and only when `download` is omitted or `false`; `?download=true` forces an attachment. **Every other type is always an attachment**, whatever `download` says. All file responses carry `X-Content-Type-Options: nosniff` and `Content-Security-Policy: sandbox; default-src 'none'`.

### 12.3. Organization Images

Similar multipart upload, but the file field is nested:

```
POST /api/accounts/organization-images/
Content-Type: multipart/form-data

image.file: (binary image data)
image_type: "logo_light"
```

`image_type` is one of `logo`, `logo_light`, `logo_dark`, `logo_horizontal`, `logo_vertical`, `cover`, `favicon`, `og_image`; each type can exist once per organization profile (a second one answers **400** on `image_type`). Reads follow stored-file visibility; writes need admin+.

---

## 13. Error Handling

### 13.1. Standardized Error Format

All API errors follow a consistent JSON envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human readable description",
    "details": null
  }
}
```

`message` and `details` values are localized to the `Accept-Language` of the
request (`pt-BR` or `en`, default `en`). `code` and `details` keys are stable
identifiers — never match on `message`, always match on `code`.

Every response carries an `X-Request-ID` header (exposed through CORS). The
SPA may send its own (`[A-Za-z0-9._-]`, up to 64 characters) or let the API
generate one; showing it next to an unexpected error lets support find the
request in the API logs.

### 13.2. Error Codes

| Error code | HTTP status | `details` value |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Per-field dictionary |
| `PARSE_ERROR` | 400 | `null` — malformed request body (invalid JSON) |
| `AUTHENTICATION_ERROR` | 401 | `null` |
| `PERMISSION_DENIED` | 403 | `null` |
| `NOT_FOUND` | 404 | `null` |
| `METHOD_NOT_ALLOWED` | 405 | `null` |
| `NOT_ACCEPTABLE` | 406 | `null` |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | `null` — the `Content-Type` is not accepted by the endpoint |
| `ACCOUNT_BLOCKED` | 401 | `null` — correct password (or refresh / access token) of a blocked account; message "Your account is blocked. Contact support." |
| `ORGANIZATION_SUSPENDED` | 403 | `null` — the session's Organization is suspended; the API has already dropped it from the session (go back to the Organization selection) |
| `INVALID_STATE` | 409 | `null` — the action does not apply to the current state (already suspended, not blocked, own account…); `message` is user-facing |
| `READ_ONLY_IMPERSONATION` | 403 | `null` — a write while viewing as another user; message "Read-only while viewing as another user" |
| `IMPERSONATION_ENDED` | 403 | `{"reason": "expired" \| "user_blocked" \| "exit" \| "signed_out", "user": <target id>}` — the viewing session ended (time, blocked user); drop it and go back to `/platform/users/{user}` |
| `THROTTLED` | 429 | `null`, or `{"retry_after_seconds": n}` for a per-object cooldown (platform resend verification) |
| `INTERNAL_ERROR` | 500 | `null` |

For `VALIDATION_ERROR`, `details` contains field-level errors:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input.",
    "details": {
      "email": ["Enter a valid email address."],
      "password": ["This field is required."]
    }
  }
}
```

### 13.3. HTTP Status Codes Quick Reference

| Status | Meaning | Common Cause |
|---|---|---|
| 200 | Success | GET, PUT, PATCH |
| 201 | Created | POST |
| 204 | No Content | DELETE |
| 400 | Bad Request | Validation errors |
| 401 | Unauthorized | Missing/expired JWT |
| 403 | Forbidden | Insufficient role; suspended Organization (`ORGANIZATION_SUSPENDED`) |
| 404 | Not Found | Cross-org access or nonexistent resource |
| 409 | Conflict | `INVALID_STATE` (platform actions, invitation of a suspended Organization) |
| 429 | Too Many Requests | Invitation email cooldown |

---

## 14. Pagination

All list endpoints are paginated with `?page=` and `?page_size=` query parameters.

**Default page size:** 10  
**Maximum page size:** 100  
**Invalid values** (zero, negative, non-numeric): fall back to the default.

**Request:**
```
GET /api/accounts/members/?page=2&page_size=25
```

**Response:**
```json
{
  "count": 47,
  "next": "http://localhost:8000/api/accounts/members/?page=3&page_size=25",
  "previous": "http://localhost:8000/api/accounts/members/?page=1&page_size=25",
  "results": [
    ...
  ]
}
```

The `next` and `previous` URLs automatically preserve the `page_size` parameter.

Ordered lists (`?order_by=`) add the primary key as a tiebreaker, so rows with the same
value (same role, same name) keep a stable order across pages. A page past the end answers
**404**: after removing the last row of the last page, go back one page.

---

## 15. Form Options Endpoints

Resources with select-like fields expose `GET .../form-options-create/` and
`GET .../form-options-update/`. Each returns one key per selectable field of the
corresponding write form (create or update), so the frontend can populate dropdowns
with exactly the values the write endpoint accepts.

| Resource | Create form fields | Update form fields |
|---|---|---|
| `GET /api/accounts/invitations/form-options-{create,update}/` | `role` | `role` |
| `GET /api/accounts/organization-images/form-options-{create,update}/` | `image_type` | `image_type` |
| `GET /api/teams/team-members/form-options-{create,update}/` | `role`, `team`, `member` | `role` |
| `GET /api/accounts/members/form-options-update-role/` | — | `role` (form of `PATCH .../members/{id}/update-role/`) |

Organizations, organization profiles, teams and stored files have **no**
form-options endpoint, and members only have the update-role one. Use the regular
list endpoints when a picker is needed.
For the dropdowns of **list filters**, use `filter-options/` (see 15.5).

Permissions are the same as the resource's read permission (see
[Authentication](#3-authentication-flow)): invitations require an admin,
team-members and members update-role an active member of the session organization,
and organization-images also answer anonymous requests. Search is **disabled** on the organization-images
routes (`?image_type=<value>` only selects the field).

**Roles depend on the caller.** The `role` options of invitations (create/update)
and members update-role list only the roles the caller may assign — the same rule the
write endpoint validates: owner → `owner`, `admin`, `manager`, `member`; admin →
`manager`, `member`; manager → `member`; member → none (empty array). The frontend
does not need to filter roles by permission.

**Team members need the team.** Send `?team_id=<id>` to the team-members form options:
`role` lists the team roles the caller may assign in that team (see 11) and `member` hides
members already active in it (removed members are listed, re-adding reactivates them).
Without a valid `team_id` (missing, another organization's or inactive team) only
organization managers get roles and `member` is not narrowed.

Labels are rendered in the request language. Send `Accept-Language` (`pt-BR` or `en`)
with every request: labels and error messages localize to it, and responses echo the
active language in the `Content-Language` header. Emails do not follow this header: they
render in the recipient's profile `preferred_language` (see [6.2](#62-update-profile)),
and links inside them carry no locale prefix, so the SPA opens them in the reader's own
UI language (`cf_locale` cookie, else browser language). Schema tags and descriptions localize
only when the schema is fetched live from `GET /api/schema/` with that header — the
committed `schema.yml` file stays English.

### 15.1. Response shapes

Fields with fixed choices return a plain array:

```json
{
  "role": [
    {"value": "owner", "label": "Owner"},
    {"value": "admin", "label": "Admin"},
    {"value": "manager", "label": "Manager"},
    {"value": "member", "label": "Member"}
  ]
}
```

Relation fields return a paginated envelope. Results are scoped to the session
organization and to active records, the same rules the write endpoint validates:

```json
{
  "team": {
    "count": 12,
    "num_pages": 2,
    "page_number": 1,
    "results": [
      {"value": 7, "label": "Platform"},
      {"value": 5, "label": "Design"}
    ]
  }
}
```

### 15.2. Query parameters

| Parameter | Effect |
|---|---|
| `?<field>` | Return only that field (e.g. `?team` or `?team=`). Multiple fields can be combined. A non-empty value also filters the field (see below). |
| `?page=N` | Page of every relation field in the response. |
| `?page_size=N` | Page size (default 10, max 100). |

`page` and `page_size` apply to **all** relation fields in the response. To paginate
a single picker, combine them with field selection: `?member&page=2`. A page past
the end of a field returns that field with `results: []` (keeping `count`,
`num_pages` and the requested `page_number`), so infinite scroll can stop when
`page_number >= num_pages`. `page=0`, negative or non-numeric pages answer 404.

Filtering by value:

- **Choice fields:** the value is a regular expression matched against the label
  or the value of each option, ignoring case and accents (`?role=^ad`, `?role=owner|admin`).
  An invalid expression is matched as plain text. Matching has a timeout: an
  expression too expensive to evaluate returns no options.
- **Paginated fields:** text search by label (`?team=plat`) only works for fields
  whose serializer opted in (see 15.3). Without that configuration the value is
  ignored and the parameter only selects the field.

These parameters are documented per route in the OpenAPI schema (`schema.yml`):
one parameter per field of the route, plus `page`/`page_size` only when the route
has at least one paginated field.

### 15.3. Backend opt-in for label and search

Every paginated field declares, case by case, the field or expression used for
its label and search in the source serializer `Meta.options_extra_kwargs` (read only
by the options serializer; the write fields never see it):
`label_field_name` (str or expression), `filter_field_name` and
`filter_lookup_expr` (default `unaccent__icontains` on organization-scoped relations,
`exact` otherwise).

| Route field | Label / search |
|---|---|
| team-members `team` | `name` |
| team-members `member` | `Member.label_expression()`: `Full Name (nickname)`, falling back to the full name, the nickname or the translated role |

Search on organization-scoped paginated fields ignores case and accents
(`?team=gestao` matches "Gestão"), through the `unaccent__icontains` lookup
(PostgreSQL `unaccent`).

Relations to models without `organization_id` (e.g. `User`, `Organization`) must
declare how they are scoped: `options_extra_kwargs = {'<field>':
{'organization_lookup': 'members__organization_id'}}` (a path to the organization).
Otherwise the API refuses to start, unless the field is explicitly marked global with
`{'organization_scoped': False}`. Extra conditions on the same related row go in
`organization_filters` (e.g. `{'members__is_active': True}`). Without a session
organization, relation options are always empty. A key of `options_extra_kwargs`
that is not a field/filter, or an unknown kwarg, also makes the API refuse to start.

Choice fields accept `choices_filter`, a callable `(choices, context) -> choices`
that narrows the options per request before the `?<field>=` search (e.g.
`assignable_role_choices` for roles). Custom `@action`s named in the ViewSet
`options_actions` get their own route: `form-options-<url_path>/` for write actions,
`<url_path>/filter-options/` for `GET` actions (with the action permissions).

### 15.4. Migration from `/choices/`

The legacy `GET /api/<resource>/choices/` endpoints were removed (no alias).

| Before | After |
|---|---|
| `GET /api/accounts/invitations/choices/` | `GET /api/accounts/invitations/form-options-create/` (`role`) |
| `GET /api/teams/team-members/choices/` | `GET /api/teams/team-members/form-options-create/` (`team`, `member`, `role`) |
| Hardcoded role list of the member role editor | `GET /api/accounts/members/form-options-update-role/` (`role`) |
| `GET /api/accounts/{organizations,members}/choices/`, `GET /api/teams/teams/choices/`, ... | List endpoint of the resource |
| Response `{count, next, previous, results}` | Object keyed by field; array for choices, `{count, num_pages, page_number, results}` for relations |

### 15.5. Filter options (list filters)

Resources whose list has select-like filters expose `GET .../filter-options/`. It
returns one key per filter of the list endpoint, **named after the list query
parameter**, so the value of an option can be sent as-is to the list:
`GET .../filter-options/` → `{"role": [{"value": "admin", ...}]}` →
`GET .../?role=admin`.

| Route | Keys |
|---|---|
| `GET /api/accounts/invitations/filter-options/` | `role`, `role__in`, `order_by` |
| `GET /api/accounts/members/filter-options/` | `organization`, `user`, `role`, `role__in`, `order_by` |
| `GET /api/accounts/organization-images/filter-options/` | `image_type`, `organization`, `order_by` |
| `GET /api/accounts/organizations/filter-options/` | `order_by` |
| `GET /api/accounts/organization-profiles/filter-options/` | `order_by` |
| `GET /api/teams/teams/filter-options/` | `organization`, `order_by` |
| `GET /api/teams/team-members/filter-options/` | `team`, `member`, `role`, `role__in`, `order_by` |
| `GET /api/accounts/invitations/received/filter-options/` | `role`, `role__in`, `order_by` (filters of `GET .../invitations/received/`) |

Stored files have no filter-options endpoint.

- **Shapes, field selection, pagination and search** are the same as the form
  options (15.1–15.2): choice filters return an array, relation filters a paginated
  envelope scoped to the session organization and active records.
- `role` and `role__in` return the same options: `role` takes one value, `role__in`
  a comma-separated list (`?role__in=admin,member`) **on the list endpoint**. On
  `filter-options/` the value of `?role__in=` is a search regex like any other
  choice field, not a CSV: send `?role__in` (empty) to select the field.
- `order_by` lists every sort option of the list, ascending (`email`) and
  descending (`-email`).
- Text filters (`*__icontains`, `name`...), boolean, date and number filters have
  no options and are not returned; neither are custom (`method=`) filters unless
  they declare their own choices.
- Permissions are the same as the list of the resource (the route answers with the
  same status code as `GET .../`); `received/filter-options/` only requires an
  authenticated user (no session organization needed), like `received/`.
- Options do not depend on the caller role, except invitations `role`/`role__in`:
  the invitation list only holds invitations with a role the caller may assign, so
  the filter lists only those (same rule as the form options, 15). Members and
  received invitations list every role.
- Label/search of relation filters:

| Route field | Label / search |
|---|---|
| members `user` | user `full_name` (falls back to the username); only users with an **active** membership in the session organization |
| members, organization-images, teams `organization` | `name` (only the session organization) |
| team-members `team` | `name` |
| team-members `member` | `Member.label_expression()` |

The backend declares these per filter in the filterset `Meta.options_extra_kwargs`
(same keys as 15.3).

---

## 16. Dashboard

### 16.1. Overview Endpoint

`GET /api/dashboard/overview/` returns the whole Organization overview for the dashboard page
in one request: the requesting Member's header data, counts and short lists for Members, Teams
and Invitations, plus the User's pending received Invitations across all Organizations.

**Permission:** authenticated User **and** active Member of the session Organization
(`IsActiveMember`). A valid JWT without an organization context answers **403** — establish the
session organization first (see [3. Authentication Flow](#3-authentication-flow)). Method:
`GET` (and `OPTIONS` for metadata); all other methods → 405. The endpoint takes
**no query parameters**.

### 16.2. Section Gates

Each Organization section is computed with the same predicate that guards its management screen
and is returned as `null` when the Member may not see it. Render only non-null sections; never
derive section visibility from the Role on the client.

| Section | Returned when | Otherwise |
|---|---|---|
| `member` | always | — |
| `members` | active Member (`has_members_access`) | `null` |
| `teams` | active Member (`has_teams_access`) | `null` |
| `invitations` | Owner or Admin (`has_invitations_access`) | `null` |
| `received_invitations` | always (User-level, all Organizations) | — |

Invitation counts follow the same Role scoping as the Invitations list: an Admin sees Manager
and Member invitations; an Owner sees all roles.

### 16.3. Response Fields

| Field | Type | Description |
|---|---|---|
| `generated_at` | datetime | Server time of computation |
| `member.id` | integer | Requesting Member id |
| `member.role` | enum | `owner` \| `admin` \| `manager` \| `member` |
| `member.role_label` | string | Role label translated by `Accept-Language` |
| `member.created_at` | datetime | Row creation (kept for compatibility) |
| `member.joined_at` | datetime | "Member since" — start of the current membership |
| `members` | object \| null | Null without Members access |
| `members.total` | integer | Active Members |
| `members.by_role[]` | array(4) | `{ role, role_label, count }` — always the four Roles in hierarchy order, zeros included |
| `members.recent[]` | array(≤5) | `{ id, full_name, email, nickname, role, role_label, created_at, joined_at }` |
| `teams` | object \| null | Null without Teams access |
| `teams.total` | integer | Active Teams |
| `teams.mine_count` | integer | Teams the Member belongs to |
| `teams.mine[]` | array(≤5) | `{ id, name, slug, role, role_label, member_count }` — `id` is the **Team** id and `role` the Team-level role |
| `invitations` | object \| null | Null without Invitations access |
| `invitations.pending` | integer | Pending visible Invitations |
| `invitations.expiring_soon[]` | array(≤5) | `{ id, email, role, role_label, expired_at }` |
| `received_invitations.pending` | integer | Pending Invitations received by the User (all Organizations) |

**Limits:** `recent`, `mine` and `expiring_soon` are capped at **5** items; "expiring soon"
means `expired_at` within the next **7 days**. Both are API constants, not query parameters.
Lists are ordered: `recent` by `joined_at` desc then `id` desc, `mine` by Team name
(case-insensitive) then `team_id`, and `expiring_soon` by `expired_at` asc then `id`.

Only active records count (soft-delete). Every number is scoped to the session Organization
except `received_invitations`, which is User-level by definition and only counts email-matched
invitations when the User's email is verified. "Pending" follows the acceptance rule of section 9: invitations
whose invitee is already an active member, and invitations of deactivated organizations, are
never counted; readmission invitations (former members) are counted.

### 16.4. Example Payload

```json
{
  "generated_at": "2026-10-09T14:03:12.123456Z",
  "member": {
    "id": 7,
    "role": "admin",
    "role_label": "Admin",
    "created_at": "2026-03-01T10:00:00Z",
    "joined_at": "2026-03-01T10:00:00Z"
  },
  "members": {
    "total": 12,
    "by_role": [
      { "role": "owner", "role_label": "Owner", "count": 1 },
      { "role": "admin", "role_label": "Admin", "count": 2 },
      { "role": "manager", "role_label": "Manager", "count": 3 },
      { "role": "member", "role_label": "Member", "count": 6 }
    ],
    "recent": [
      {
        "id": 31,
        "full_name": "Ana Lima",
        "email": "ana@acme.io",
        "nickname": "ana",
        "role": "member",
        "role_label": "Member",
        "created_at": "2026-10-08T09:12:00Z",
        "joined_at": "2026-10-08T09:12:00Z"
      }
    ]
  },
  "teams": {
    "total": 4,
    "mine_count": 2,
    "mine": [
      {
        "id": 3,
        "name": "Platform",
        "slug": "platform",
        "role": "owner",
        "role_label": "Owner",
        "member_count": 5
      }
    ]
  },
  "invitations": {
    "pending": 3,
    "expiring_soon": [
      {
        "id": 9,
        "email": "joe@acme.io",
        "role": "manager",
        "role_label": "Manager",
        "expired_at": "2026-10-11T00:00:00Z"
      }
    ]
  },
  "received_invitations": { "pending": 1 }
}
```

Sections the Member cannot see are `null` (e.g. `invitations` for a Manager) and the frontend
must not render them.

### 16.5. Errors

| Case | Status |
|---|---|
| Missing / invalid JWT | 401 |
| No session Organization, or inactive Member | 403 |
| Non-GET / non-OPTIONS method | 405 |

---

## 17. Audit Trail

Every write in the audit catalog (Organizations, profiles, images, Members, Invitations,
Teams, Team Members, StoredFiles) and every persisted security event is stored as an
immutable **Audit Event**. Reads are never audited.

### 17.1. Organization events

`GET /api/audit/events/` and `GET /api/audit/events/{id}/` — JWT **and** session
Organization, gated by `member.access.audit` (OWNER and ADMIN; others get `403`). Only the
session Organization's events are returned (another Organization's id → `404`). Writes
return `405`.

| Filter | Example | Notes |
|---|---|---|
| `created_at_after` / `created_at_before` | `2026-10-01` | Dates, inclusive; inverted range → `400` |
| `actor` | `12` | Member id (options list active Members only) |
| `action` / `action__in` | `member.role_changed,member.removed` | Action codes |
| `target_type` / `target_type__in` | `team,member` | Snake-case model names |
| `target_id` | `42` | Requires `target_type` or `target_type__in` (`400` otherwise) |

Order is fixed (newest first); pagination is the standard `{count, next, previous, results}`.
Each event also carries `organization_name` and `subject_label` (email · name), snapshots taken when it was recorded:
events survive the deletion of their Organization or subject User (`organization_id` / the subject become empty).
`GET /api/audit/events/filter-options/` describes the `actor`, `action` and `target_type`
filters (paginated `actor`).

```json
{
  "id": 981,
  "created_at": "2026-10-15T18:02:11.204Z",
  "action": "member.role_changed",
  "action_display": "Member role changed",
  "actor_type": "user",
  "actor": {"user_id": 3, "member_id": 7, "label": "Ana Lima (ana)"},
  "impersonator": null,
  "organization_id": 2,
  "target_type": "member",
  "target_id": "15",
  "target_label": "Bruno Reis",
  "changes": [
    {"field": "role", "field_display": "Role", "before": "member", "after": "manager"}
  ],
  "metadata": {},
  "ip": "203.0.113.9"
}
```

- `action_display` and `field_display` follow `Accept-Language`.
- `actor` is `null` for `actor_type: "system"`; `impersonator` is reserved (always `null`).
- `target_label` and relation values in `changes` (`{"id", "label"}`) are snapshots taken
  when the event happened, so they stay readable after renames and removals.
- Create events list the initial values (`before: null`); delete events have no changes.
- The invitee email may appear in `invitation.*` events; passwords, tokens and Invitation
  keys never do.

### 17.2. Account activity

`GET /api/accounts/users/me/activity/` — JWT only (no Organization context). Paginated
account events of the authenticated User: `auth.*` (sign-ins, failed sign-ins targeting the
account, sign-outs, password changes and resets, email verification) and
`user.profile.updated` (an email change is recorded without the email values). Same item
shape as above, with `organization_id: null`.

---

## 18. Platform Panel

Endpoints for **platform staff** (`user.platform_role` = `support` or `admin`), outside any Organization context
([ADR-009](../../docs/adr/009-platform-access-outside-organization-context.md)): JWT only — no Organization login is
needed and the session's Organization is ignored. A User with role `none` gets `403` on every route. Reads are open to
`support` and `admin`; account actions (below) need `admin` (`support` gets `403`).

The session exposes the role: `GET /api/accounts/session/` → `user.platform_role` (`none` | `support` | `admin`). Every
Organization in `organizations` (session and Organization list) carries `status` (`active` | `suspended`).

| Endpoint | Description | Query parameters |
|---|---|---|
| `GET /api/platform/overview/` | Platform numbers (`organizations_total`, `organizations_suspended`, `organizations_new_7d/30d`, `organizations_active_30d`, `users_total`, `users_blocked`, `users_new_7d/30d`) | — |
| `GET /api/platform/organizations/` | Organizations with `owner {id, full_name, email, member_id, member_since}`, `active_members_count`, `last_access_at`, `status`, `is_deleted` | `search` (name, slug, owner email), `status`, `created_at_after`, `created_at_before`, `deleted` (default hides soft-deleted), `order_by` (`name`, `created_at`, `last_access_at`, `active_members_count`, `-` for descending), `page`, `page_size` |
| `GET /api/platform/organizations/{id}/` | Detail: list fields + `profile`, `counts {active_members, teams, pending_invitations}`, `storage_bytes`, `suspension {suspended_at, suspended_by, reason}` or `null` | — |
| `GET /api/platform/organizations/{id}/members/` | Members (`user {id, full_name, email}`, `role`, `joined_at`, `last_login_at`, `is_active`) | `search`, `is_active`, `exclude_owner`, `page` |
| `GET /api/platform/organizations/{id}/teams/` | Active teams with `members_count` | `page` |
| `GET /api/platform/organizations/{id}/invitations/` | Pending invitations | `page` |
| `GET /api/platform/users/` | Users with `organizations_count`, `platform_role`, `is_blocked`, `is_deleted`, `email_verified` | `search`, `verified`, `blocked`, `platform_role`, `date_joined_after`, `date_joined_before`, `deleted`, `order_by` (`full_name`, `date_joined`, `last_login`), `page`, `page_size` |
| `GET /api/platform/users/{id}/` | Detail: list fields + `blocking {blocked_at, blocked_by, reason}` or `null`, `memberships[]`, `can_impersonate`, `can_block` (for the requesting staff member) | — |
| `GET /api/platform/audit-events/` | Every Audit Event (Organization and account) with `organization {id, name}` or `null` and `subject_user` | `created_at_after`, `created_at_before`, `organization`, `user` (actor or subject), `scope` (`account` \| `organization`), `action`, `action__in`, `target_type`, `target_type__in`, `page` |

`GET /api/platform/audit-events/filter-options/` returns the audit filter choices: `action` / `action__in` with labels, `scope`, and `organization` paginated (`?organization=<name>&page=`), same envelope as the other `filter-options` routes.

Inverted periods answer `400` with `created_at` / `date_joined` field errors. Use the Organization detail's
`members` route with `is_active=true&exclude_owner=true&search=` for the ownership-transfer picker.

### 18.1. Account actions (platform admin)

Every action is a `POST` with a JSON body, answers `200` with the refreshed detail (Organization or User) and records
an Audit Event with `actor_type: "platform"` and `metadata.reason` when a reason is given. `reason` is trimmed, at most
500 characters; "required" means blank is refused with `VALIDATION_ERROR` (`details.reason`). Reasons are internal: they
never appear in emails.

| Endpoint | Body | Errors |
|---|---|---|
| `POST /api/platform/organizations/{id}/suspend/` | `reason` (required) | `409` "This organization is already suspended." |
| `POST /api/platform/organizations/{id}/reactivate/` | `reason` (optional) | `409` "This organization is already active." |
| `POST /api/platform/organizations/{id}/transfer-ownership/` | `member` (active Member of the Organization, not the owner), `reason` (required) | `400` `details.member` |
| `POST /api/platform/users/{id}/block/` | `reason` (required) | `409` "This user is already blocked." / "You can't block your own account." |
| `POST /api/platform/users/{id}/unblock/` | `reason` (optional) | `409` "This user is not blocked." |
| `POST /api/platform/users/{id}/end-sessions/` | `reason` (optional) | — |
| `POST /api/platform/users/{id}/resend-verification/` | `reason` (optional) | `409` (already verified), `429` `THROTTLED` with `details.retry_after_seconds` |
| `POST /api/platform/users/{id}/force-password-reset/` | `reason` (optional) | — |

Effects the SPA must handle:

- **Suspension:** Members of the Organization get `403 ORGANIZATION_SUSPENDED` on their next Organization request (and
  on its login); the session no longer holds it, and `GET /api/accounts/session/` answers `organization: null` with the
  Organization listed as `status: "suspended"`. Invitations of a suspended Organization can't be accepted (`409
  INVALID_STATE` "This organization is suspended, so the invitation can't be accepted."). The owner is emailed on
  suspension and reactivation; both owners on a transfer (new owner Owner, previous owner Admin).
- **Block / end sessions / force reset:** every access token issued before the action is refused at once
  (`AUTHENTICATION_ERROR`) and refresh tokens are blacklisted; signing in again answers `ACCOUNT_BLOCKED` while the
  account is blocked. Deleted accounts refuse every action (`409` "This user account is deleted."). Unblocking does not restore ended sessions. Force reset also makes the current password unusable and emails
  a reset link.


### 18.2. View as a user (impersonation)

Platform staff (`support` or `admin`) can view the app as a User, read-only, for at most 30 minutes
([ADR-009](../../docs/adr/009-platform-access-outside-organization-context.md)). The viewing session lives in the
staff member's Django session (`sessionid`): their own JWT stays the credential, no token is ever issued for the User.

| Endpoint | Body | Response / errors |
|---|---|---|
| `POST /api/platform/users/{id}/impersonate/` | `reason` (required, ≤ 500) | `200` the `Session` payload as the User (`organization: null`); `409` "This user can't be viewed (platform staff, blocked or deleted)." / "You already have an active viewing session." |
| `POST /api/platform/impersonation/exit/` | — | `200` `{user: <target id>}` (go back to `/platform/users/{user}`); `409` without an active viewing session |

While viewing:

- Every request acts as the User (`request.user`): their Organizations, Roles, `member.access`. The platform panel is
  not available (the User has no platform role) until exit.
- `GET /api/accounts/session/` carries `impersonation {id, target {id, full_name}, staff {id, full_name}, expires_at}`
  (`null` otherwise); the remaining time comes from `expires_at`.
- Writes answer `403 READ_ONLY_IMPERSONATION`, except entering an Organization
  (`POST /api/accounts/organizations/{id}/login/`, which keeps the Member's `last_login_at`), logout (ends the viewing
  session with `signed_out`) and the exit route.
- A suspended Organization answers `403 ORGANIZATION_SUSPENDED` as for the User; the viewing session goes on.
- After 30 minutes, or when the User is blocked, the next request answers `403 IMPERSONATION_ENDED`
  (`details.reason` `expired` | `user_blocked`, `details.user`) and the session is the staff member's again.
- Start, end and expiry are account events of the User (`user.impersonation_started` with the reason,
  `user.impersonation_ended`, `user.impersonation_expired`), visible in their account activity; events recorded while
  viewing carry `impersonator`.
---

## 19. Troubleshooting

### 19.1. Cookies Not Being Sent

- Check that `withCredentials: true` (Angular) or `credentials: 'include'` (Fetch) is set on all requests that need the session.
- Verify the SameSite + Secure configuration via `GET /api/accounts/session/config/` (public endpoint, no auth required; the diagnostics are only returned with `DEBUG=True`).
- In development (HTTP), both `SameSite=Lax` and `Secure=False` are required. In production (HTTPS), `SameSite=None` and `Secure=True`.

### 19.2. CORS Errors

- Verify `CORS_ALLOWED_ORIGINS` in `.env` includes the frontend origin (e.g., `http://localhost:4200`).
- Check the browser console for `Access-Control-Allow-Origin` headers.
- With `DEBUG=True`, the `/api/accounts/session/config/` endpoint returns the current `cors_allowed_origins` setting.

### 19.3. 404 on Org-Scoped Endpoints

This is the most common issue. A 404 (not 403) on org-scoped resources usually means the `organization_id` is not in the session.

- Verify Step 3 (organization login) was completed successfully.
- Check `GET /api/accounts/session/` — if `organization` and `member` are `null`, the session has no active organization context.

### 19.4. Token Expired

- A 401 response means the access token has expired.
- Attempt a token refresh via `POST /api/auth/token/refresh/`.
- If the refresh succeeds, store the new tokens and retry the original request.
- If the refresh fails, redirect the user to the login page.
- Implement this as an `HttpInterceptor` to handle it transparently across all requests.
