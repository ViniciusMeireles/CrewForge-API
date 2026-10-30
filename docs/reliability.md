# Reliability

This document defines CrewForge's reliability contracts: error handling,
performance guidelines, caching, logging, and observability.

---

## Table of Contents

- [Error Handling](#error-handling)
- [Error Response Format](#error-response-format)
- [Performance Guidelines](#performance-guidelines)
- [Database Transactions](#database-transactions)
- [Caching](#caching)
- [Health Probes](#health-probes)
- [Logging](#logging)
- [Sentry Integration](#sentry-integration)
- [Housekeeping](#housekeeping)
- [Rate Limiting](#rate-limiting)

---

## Error Handling

### Rules

- Never catch bare `Exception`. Catch specific exception types
  (`IOError`, `FileNotFoundError`, `ValueError`, `ObjectDoesNotExist`, etc.).
- Always verify that objects returned by helper functions are not `None` before
  accessing attributes (e.g., `get_member(request)` may return `None`).
- Use Django's built-in exceptions (`Http404`, `PermissionDenied`) for HTTP
  error responses instead of raising generic exceptions.
- Never expose stack traces in production (`DEBUG=False`).
- For permission denied, return 403.
- For resources not found, return **404** (not 403) to avoid resource enumeration.

---

## Error Response Format

All API errors use a standardized JSON envelope implemented by
`apps/generics/exceptions.crewforge_exception_handler`:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human readable description",
    "details": {"field": "specific error"}
  }
}
```

`message` and `details` values follow the request `Accept-Language`
(`pt-BR`/`en`, default `en`); `code` and `details` keys are never translated.

### Error Codes

| Error code | HTTP status | `details` |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Per-field dict |
| `AUTHENTICATION_ERROR` | 401 | `null` |
| `PERMISSION_DENIED` | 403 | `null` |
| `NOT_FOUND` | 404 | `null` |
| `PARSE_ERROR` | 400 | `null` (malformed body) |
| `METHOD_NOT_ALLOWED` | 405 | `null` |
| `NOT_ACCEPTABLE` | 406 | `null` |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | `null` |
| `THROTTLED` | 429 | `null` |
| `INTERNAL_ERROR` | 500 | `null` |

---

## Performance Guidelines

### Database Queries

- Add `select_related` for `ForeignKey`/`OneToOneField` in viewset querysets
  to avoid N+1 queries.
- Add `prefetch_related` for `ManyToManyField` in viewset querysets.
- Example:
  ```python
  queryset = Member.objects.select_related('user', 'organization').all()
  ```

### Indexes

- Add `db_index=True` or `Meta.indexes` for fields used in frequent lookups,
  filters, or unique constraints (e.g., `slug`, `email`, `key`).
- Composite indexes should be defined in `Meta.indexes` for fields often
  queried together.

### When to Optimize

- Profile before optimizing; do not add indexes or caching speculatively.
- Cache configuration will be documented in `specs/` when implemented.

---

## Database Transactions

- Use `@transaction.atomic` for operations requiring multi-model consistency.
- For bulk operations, consider `transaction.on_commit()`.
- Always check `connection.atomic_blocks` in sensitive contexts.
- Avoid unnecessary transactions in read-only operations.

---

## Caching

The default cache is Redis (`CACHE_URL`, default `redis://redis:6379/1`), shared
by every process, so throttle counters and cooldowns hold across Gunicorn workers
and Celery. Tests use `LocMemCache`. Database connections are reused for
`CONN_MAX_AGE` seconds (default `60`) with health checks.

Response caching is not used yet. When it is:

- Add cache only after profiling identifies bottlenecks.
- Implement cache invalidation on model changes.
- Cache key naming: `crewforge:{app}:{model}:{action}:{identifier}`

### TTL Guidelines

| Data type | TTL |
|---|---|
| List endpoints | 5-15 min |
| Detail endpoints | 5 min |

### Rules

- Never cache sensitive data (passwords, tokens).
- Target cache hit ratio > 80% for hot data.

---

## Health Probes

`HealthCheckMiddleware` (after `RequestIdMiddleware`, before host validation
and the HTTPS redirect) answers two unauthenticated `GET` probes:

| Path | Checks | Response |
|---|---|---|
| `/healthz` | The process answers | `200 {"status": "ok"}` |
| `/readyz` | `SELECT 1` and a cache set/get | `200 {"status": "ok"}` or `503 {"status": "unavailable"}` |

They reveal nothing else, are never throttled and accept any `Host`, so the
image `HEALTHCHECK` and orchestrators can call `127.0.0.1:8000`.

---

## Logging

Django logs one JSON object per line on stdout (`apps.generics.logging.JsonFormatter`):

```json
{"timestamp": "2026-10-30T01:16:01+00:00", "level": "WARNING", "logger": "django.request",
 "message": "Unauthorized: /api/accounts/invitations/999/", "request_id": "smoke-6", "status_code": 401}
```

Extra attributes (`extra={...}`, such as `security_event`) become keys, and
exceptions go under `exception`. Gunicorn's own process and access lines keep
Gunicorn's format (they do not start with `{`).

### Request ID

`RequestIdMiddleware` keeps an incoming `X-Request-ID` that matches
`^[A-Za-z0-9._-]{1,64}$`, otherwise generates a UUID. It echoes the id in the
response and adds it to every log line of the request (`request_id`), including
the `django.request` lines written after the middleware chain returns.

### Standards

- Use `logging.getLogger(__name__)` for all loggers.
- Never log passwords, tokens, or sensitive data.
- Client errors (4xx) log no traceback; the exception handler logs a traceback
  only for 5xx responses.
- Authentication events use `log_security_event()` (`security` logger); see
  [`security.md`](./security.md#security-logging).
- Levels: `LOG_LEVEL` (root, default `INFO`) and `SECURITY_LOG_LEVEL`.

### Log Levels

| Level | Use case |
|---|---|
| `DEBUG` | Query strings, debug variables |
| `INFO` | CRUD operations, login/logout |
| `WARNING` | Unexpected but non-critical situations |
| `ERROR` | Treated exceptions (reach Sentry when enabled) |
| `CRITICAL` | Critical failures (Sentry + alert) |

---

## Sentry Integration

Optional. `config/settings/observability.py` `init_sentry()` runs from the
production settings and initializes Sentry only when `SENTRY_DSN` is set:

- `send_default_pii=False`: no user data, cookies or headers;
- `SENTRY_ENVIRONMENT` and `SENTRY_RELEASE` (for example the image tag) tag events;
- unhandled exceptions and `ERROR` log records are reported; empty DSN = disabled.

---

## Housekeeping

Celery beat (`CELERY_BEAT_SCHEDULE` in `config/settings/base.py`) runs:

| Task | Command | Schedule |
|---|---|---|
| `apps.accounts.tasks.flush_expired_tokens` | `flushexpiredtokens` | daily 03:00 |
| `apps.accounts.tasks.clear_sessions` | `clearsessions` | daily 03:15 |
| `apps.accounts.tasks.expire_invitations` | `expire_invites` | hourly |

`send_email` retries SMTP and network failures (`SMTPException`, `OSError`) up
to 3 times with backoff, and refuses email classes outside `apps.accounts.emails`.

---

## Rate Limiting

### Invitation Email Cooldown

The `POST /api/accounts/invitations/{id}/send-email/` endpoint enforces a
60-second cooldown between email sends:

| Condition | Response |
|---|---|
| Within cooldown | `429` with `retry_after_seconds` |
| Expired invitation | `400` |
| Already accepted | `400` |
| Success | `200` |

### General Rate Limiting

Rate limiting configuration is planned for future implementation. When
implemented, follow:

- Use Django REST Framework's throttling classes
- Configure per-user and per-organization limits
- Return `429` with `Retry-After` header
