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
- [Logging](#logging)
- [Sentry Integration](#sentry-integration)
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

### Error Codes

| Error code | HTTP status | `details` |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Per-field dict |
| `AUTHENTICATION_ERROR` | 401 | `null` |
| `PERMISSION_DENIED` | 403 | `null` |
| `NOT_FOUND` | 404 | `null` |
| `METHOD_NOT_ALLOWED` | 405 | `null` |
| `NOT_ACCEPTABLE` | 406 | `null` |
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

Caching is planned for future implementation. When implemented, follow:

- Add cache only after profiling identifies bottlenecks.
- Use Redis as cache backend.
- Implement cache invalidation on model changes.
- Cache key naming: `crewforge:{app}:{model}:{action}:{identifier}`

### TTL Guidelines

| Data type | TTL |
|---|---|
| Sessions | 15 min |
| List endpoints | 5-15 min |
| Detail endpoints | 5 min |

### Rules

- Never cache sensitive data (passwords, tokens).
- Target cache hit ratio > 80% for hot data.

---

## Logging

### Standards

- Use `logging.getLogger(__name__)` for all loggers.
- Never log passwords, tokens, or sensitive data.
- Add `request_id` or `correlation_id` to API request logs for tracing.

### Log Levels

| Level | Use case |
|---|---|
| `DEBUG` | Query strings, debug variables |
| `INFO` | CRUD operations, login/logout |
| `WARNING` | Unexpected but non-critical situations |
| `ERROR` | Treated exceptions (send to Sentry) |
| `CRITICAL` | Critical failures (send to Sentry + alert) |

---

## Sentry Integration

When implementing Sentry error tracking, follow these patterns:

- Sentry SDK initialization goes in `config/settings/base.py` with environment-based config
- Use `SENTRY_DSN` environment variable to enable/disable (empty = disabled)
- Create middleware in `apps/generics/middleware/` to add user and organization context
- Set `send_default_pii=False` to avoid capturing sensitive user data
- Use different DSNs for production vs development environments
- See `specs/sentry_integration_spec.md` for detailed implementation guide

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
