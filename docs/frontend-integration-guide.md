# Frontend Integration Guide

## 1. Overview

CrewForge is a Django REST API that uses a **two-layer authentication model**:

1. **JWT tokens** (`Authorization: Bearer <access>`) for API authentication.
2. **Django session cookie** (`sessionid`) for organization context.

All endpoints are prefixed with `/api/`.

The API is organized into three main namespaces:

| Prefix | Purpose |
|---|---|
| `/api/auth/` | Authentication, token refresh, password reset |
| `/api/accounts/` | Organizations, members, invitations, files, user profile, signup |
| `/api/teams/` | Teams and team memberships |

---

## 2. Getting Started

### 2.1. Environment Checklist

Required variables in `.env` for frontend integration:

| Variable | Example value | Purpose |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | `http://localhost:4200` | Browser CORS policy |
| `FRONTEND_URL` | `http://localhost:4200` | Base URL for invitation accept links |
| `FRONTEND_RESET_URL` | `http://localhost:4200/reset-password` | Base URL for password reset links |
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
| `SESSION_COOKIE_SAMESITE` | `Lax` | `None` |
| `CSRF_COOKIE_SAMESITE` | `Lax` | `None` |
| `SESSION_COOKIE_SECURE` | `False` | `True` |
| `CSRF_COOKIE_SECURE` | `False` | `True` |

> **Warning:** `SameSite=None` + `Secure=False` is invalid. Modern browsers silently reject such cookies. Development must use `Lax` because HTTP cannot set Secure cookies.

The public endpoint `GET /api/accounts/session/config/` returns the current cookie and CORS settings. Use it for debugging connectivity issues.

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

Store both tokens. Attach the access token to all subsequent requests:

```
Authorization: Bearer eyJhbGciOiJI...
```

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

#### 3.3.1. Filtering Organizations

The list endpoint supports the following query parameters:

| Parameter | Type | Description |
|---|---|---|
| `my_organizations` | `boolean` | When `true`, returns only organizations where the authenticated user is an active member (`false` by default) |
| `name` | `string` | Exact match on name |
| `name__icontains` | `string` | Case-insensitive name contains |
| `slug` | `string` | Exact match on slug |
| `slug__icontains` | `string` | Case-insensitive slug contains |
| `is_active` | `boolean` | Filter by active status |

**Example — list only organizations the user belongs to:**

```
GET /api/accounts/organizations/?my_organizations=true
```

This is useful for the organization selection screen (Step 2 of the auth flow),
especially when the user has a large number of organizations.

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
    "last_login_at": "2026-07-10T12:00:00Z"
  }
}
```

### 3.5. After Authentication

All subsequent requests need both:

```
Authorization: Bearer eyJhbGciOiJI...
Cookie: sessionid=<value>   ← sent automatically with withCredentials
```

### 3.6. Session State

Use this endpoint to restore the application state after a page refresh:

```
GET /api/accounts/session/
```

Returns the same shape as the login response (user, organizations, organization, member). If the user is authenticated but has no active organization, `organization` and `member` are `null`.

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

**Response (200):** `{"detail": "Password reset email sent."}`

Returns 200 whether the email exists or not (security measure). The email contains a link with `uid` and `token` query parameters.

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

The JWT tokens are nested inside `user.auth_token`. After signup, the frontend should store the tokens and call the organization login (Step 3) to establish the session.

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
  "first_name": "John",
  "last_name": "Doe"
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
  "email": "jonathan@example.com"
}
```

`username` and `id` are read-only. Partial updates are supported.

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

Validates that the new password differs from the current one and is at least 8 characters long.

---

## 7. Organization Management

| Action | Endpoint | Permission |
|---|---|---|
| List | `GET /api/accounts/organizations/` | Authenticated user (member of) |
| Create | `POST /api/accounts/organizations/` | Any authenticated user |
| Retrieve | `GET /api/accounts/organizations/{id}/` | Member of the organization |
| Update | `PUT/PATCH /api/accounts/organizations/{id}/` | Admin+ role |
| Login | `POST /api/accounts/organizations/{id}/login/` | Active member |
| Choices | `GET /api/accounts/organizations/choices/` | Authenticated user |

---

## 8. Member Management

| Action | Endpoint | Permission |
|---|---|---|
| List | `GET /api/accounts/members/` | Member of the org |
| Retrieve | `GET /api/accounts/members/{id}/` | Member of the org |
| Update role | `PATCH /api/accounts/members/{id}/` | Sufficient role hierarchy |
| Create via invite | `POST /api/accounts/members/create-with-invite/{invitation_key}/` | No auth required |
| Choices | `GET /api/accounts/members/choices/` | Member of the org |

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

**Response (200):** Same shape as signup: nested `user` with `auth_token` containing JWT tokens, plus membership fields.

---

## 9. Invitations

| Action | Endpoint | Permission |
|---|---|---|
| List | `GET /api/accounts/invitations/` | Role-scoped (manager+ sees their level and below) |
| Create | `POST /api/accounts/invitations/` | Admin+ (or manager for member-level invites) |
| Retrieve | `GET /api/accounts/invitations/{id}/` | Sufficient role |
| Update | `PUT/PATCH /api/accounts/invitations/{id}/` | Sufficient role |
| Delete | `DELETE /api/accounts/invitations/{id}/` | Sufficient role |
| Send email | `POST /api/accounts/invitations/{id}/send-email/` | Manager+ |
| Choices | `GET /api/accounts/invitations/choices/` | Member of the org |

### Send Email Cooldown

`POST /api/accounts/invitations/{id}/send-email/` has a 60-second cooldown:

| Status | Meaning |
|---|---|
| **200** | Email sent successfully |
| **400** | Invitation expired or user already a member |
| **404** | Invitation not found |
| **429** | Cooldown active (include `retry_after_seconds` in response) |

Invitations are looked up by primary key (`id`), not by the UUID `key`.

---

## 10. Teams

| Action | Endpoint | Permission |
|---|---|---|
| List | `GET /api/teams/teams/` | Member of the org |
| Create | `POST /api/teams/teams/` | Member of the org |
| Retrieve | `GET /api/teams/teams/{id}/` | Member of the org |
| Update | `PUT/PATCH /api/teams/teams/{id}/` | Admin+ |
| Delete | `DELETE /api/teams/teams/{id}/` | Admin+ |
| Choices | `GET /api/teams/teams/choices/` | Member of the org |

Creating a team auto-creates a `TeamMember` record with `OWNER` role for the creator.

---

## 11. Team Members

| Action | Endpoint | Permission |
|---|---|---|
| List | `GET /api/teams/team-members/` | Member of the org |
| Create | `POST /api/teams/team-members/` | Manager+ |
| Retrieve | `GET /api/teams/team-members/{id}/` | Member of the org |
| Update role | `PATCH /api/teams/team-members/{id}/` | Sufficient role |
| Delete | `DELETE /api/teams/team-members/{id}/` | Admin+ |
| Choices | `GET /api/teams/team-members/choices/` | Member of the org |

Re-adding a previously removed (soft-deleted) team member reactivates their membership.

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

### 12.2. Download

```
GET /api/accounts/stored-files/{uuid}/file/?download=true
Authorization: Bearer eyJhbGciOiJI...
```

Requires the `Authorization` header. Cannot use a plain `<a href>` tag — the frontend must fetch via `HttpClient` with `responseType: 'blob'`.

When `?download=true`, the server sets `Content-Disposition: attachment`. When omitted or `false`, the file is served inline.

### 12.3. Organization Images

Similar multipart upload, but the file field is nested:

```
POST /api/accounts/organization-images/
Content-Type: multipart/form-data

image.file: (binary image data)
image.type: "logo"
```

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

### 13.2. Error Codes

| Error code | HTTP status | `details` value |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Per-field dictionary |
| `AUTHENTICATION_ERROR` | 401 | `null` |
| `PERMISSION_DENIED` | 403 | `null` |
| `NOT_FOUND` | 404 | `null` |
| `METHOD_NOT_ALLOWED` | 405 | `null` |
| `NOT_ACCEPTABLE` | 406 | `null` |
| `THROTTLED` | 429 | `null` |
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
| 403 | Forbidden | Insufficient role |
| 404 | Not Found | Cross-org access or nonexistent resource |
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

---

## 15. Choices Endpoints

Every resource provides a `GET /api/<resource>/choices/` endpoint that returns value/label pairs. Useful for populating dropdowns and select inputs.

**Examples:**

```
GET /api/accounts/organizations/choices/
GET /api/accounts/members/choices/
GET /api/accounts/invitations/choices/
GET /api/teams/teams/choices/
GET /api/teams/team-members/choices/
```

**Response (paginated):**
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {"value": "1", "label": "Acme Corp"},
    {"value": "2", "label": "Globex Inc"},
    {"value": "3", "label": "Initech"}
  ]
}
```

---

## 16. Troubleshooting

### 16.1. Cookies Not Being Sent

- Check that `withCredentials: true` (Angular) or `credentials: 'include'` (Fetch) is set on all requests that need the session.
- Verify the SameSite + Secure configuration via `GET /api/accounts/session/config/` (public endpoint, no auth required).
- In development (HTTP), both `SameSite=Lax` and `Secure=False` are required. In production (HTTPS), `SameSite=None` and `Secure=True`.

### 16.2. CORS Errors

- Verify `CORS_ALLOWED_ORIGINS` in `.env` includes the frontend origin (e.g., `http://localhost:4200`).
- Check the browser console for `Access-Control-Allow-Origin` headers.
- The `/api/accounts/session/config/` endpoint returns the current `cors_allowed_origins` setting.

### 16.3. 404 on Org-Scoped Endpoints

This is the most common issue. A 404 (not 403) on org-scoped resources usually means the `organization_id` is not in the session.

- Verify Step 3 (organization login) was completed successfully.
- Check `GET /api/accounts/session/` — if `organization` and `member` are `null`, the session has no active organization context.

### 16.4. Token Expired

- A 401 response means the access token has expired.
- Attempt a token refresh via `POST /api/auth/token/refresh/`.
- If the refresh succeeds, store the new tokens and retry the original request.
- If the refresh fails, redirect the user to the login page.
- Implement this as an `HttpInterceptor` to handle it transparently across all requests.
