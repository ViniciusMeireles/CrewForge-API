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
| TD-001 | Form-options default label is `str(obj)`; `Member.__str__` reads `user` and `organization`, so `member` options on team-members run 2 extra queries per item. Configure `label_field_name` or `select_related` | low | s | 2026-09-30 | `apps/generics/fields/options.py` | — |
| TD-002 | Form-options opt-in (`label_field_name`, `filter_field_name`, `filter_lookup_expr`) is read from the source serializer `Meta.extra_kwargs`, which also reaches the write `PrimaryKeyRelatedField` and raises `TypeError`. Add a dedicated `Meta` key merged only into the options serializer before any serializer uses it | medium | s | 2026-09-30 | `apps/generics/serializers/options.py` | — |
| TD-003 | Form-options relations to models without `organization_id` (`User`, `Organization`) are only filtered by `is_active`, which would list records from every tenant. Today they are avoided with `options_actions = ()` (`MemberViewSet`, `StoredFileViewSet`) and nested-field exclusion; a framework-level guard is missing | high | s | 2026-09-30 | `apps/generics/mixins/views.py` | — |

---

## Resolved Debt

| ID | Description | Resolved | PR/Issue |
|----|-------------|----------|----------|
| — | — | — | — |
