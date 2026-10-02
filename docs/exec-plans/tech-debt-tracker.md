# Tech Debt Tracker

Known technical debt, prioritized by impact and effort.

---

## Table of Contents

- [How to use](#how-to-use)
- [Active Debt](#active-debt)
- [Resolved Debt](#resolved-debt)

---

## How to use

1. Add new debt items under **Active Debt** with all fields filled
2. When fixing debt, move the item to **Resolved Debt** with the fix date
3. Priorities: `critical`, `high`, `medium`, `low`
4. Effort: `xs` (< 1h), `s` (1-4h), `m` (1-2d), `l` (3-5d), `xl` (> 1d)

---

## Active Debt

| ID | Description | Priority | Effort | Identified | Module | PR/Issue |
|----|-------------|----------|--------|------------|--------|----------|
| — | *No active debt* | — | — | — | — | — |

---

## Resolved Debt

| ID | Description | Resolved | PR/Issue |
|----|-------------|----------|----------|
| TD-001 | Form-options label `str(obj)` caused N+1 on team-members `member`; it now uses `Member.label_expression()` | 2026-10-01 | — |
| TD-002 | Form-options opt-in moved to the dedicated `Meta.options_extra_kwargs`, which never reaches the write fields | 2026-10-01 | — |
| TD-003 | Organization-scoped form options refuse relations to models without `organization_id` at startup (`ImproperlyConfigured`) unless the field declares `organization_scoped: False` | 2026-10-01 | — |
| TD-004 | A page past the end of a paginated options field returns an empty page for that field instead of a 404 for the whole response | 2026-10-01 | — |
| TD-005 | Form-options build errors raise `ImproperlyConfigured` naming the ViewSet; unmapped value types fall back to `str` (more Django fields mapped) | 2026-10-01 | — |
| TD-006 | `PaginatedOptionsBaseSerializer.get_pagination_class()` reads `DEFAULT_PAGINATION_CLASS` at runtime | 2026-10-01 | — |
| TD-007 | Constraint `IntegrityError` maps to a 400 with the constraint message (global handler); team names need a letter or number; `member_count` ignores inactive organization members | 2026-10-01 | — |
| TD-008 | View descriptions in members/team-members use `format_lazy` and are translatable | 2026-10-01 | — |
| TD-009 | Relations scoped through a path declare `organization_lookup` (options via `Meta.options_extra_kwargs`, write fields via `extra_kwargs`); the options startup check accepts and validates it | 2026-10-02 | — |
| TD-010 | `apps/accounts/serializers/user.py` covered by unit tests (password validation, `is_valid`, create/update with password) | 2026-10-02 | — |
| TD-011 | Removed the dead `UserGetOrCreateSerializer` and the unreachable "user already exists" block of `UserSerializer.is_valid` (the model `UniqueValidator` always ran first); members join through invitations | 2026-10-02 | — |
