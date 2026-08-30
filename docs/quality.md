# Quality Score

This document defines CrewForge's quality targets, coverage requirements,
and quality gates. Agents must meet these standards before considering work
complete.

---

## Table of Contents

- [Coverage Targets](#coverage-targets)
- [Quality Gates](#quality-gates)
- [Test Coverage Requirements](#test-coverage-requirements)
- [Quality Grading](#quality-grading)

---

## Coverage Targets

### Minimum Coverage by Module

| Module | Minimum Target |
|--------|----------------|
| Models | 85% |
| Views/ViewSets | 70% |
| Serializers | 60% |
| Permissions | 50% |
| Utils/Helpers | 100% |
| Overall | 88% |

### How to Measure

```bash
# Local with coverage
make l_test

# Parallel without coverage (faster iteration)
make l_test_parallel_nocov
```

Coverage configuration is in `pyproject.toml`:

```ini
[tool.coverage.run]
branch = true
omit = [
    "*/management/*",
    "*/tests/*",
    "*/__init__.py",
    "*/settings/*",
    "manage.py",
    "wsgi.py",
    "asgi.py",
]
```

---

## Quality Gates

### Pre-Merge Requirements

Every change must pass these checks before merge:

| Gate | Command | Blocking |
|------|---------|----------|
| Lint + format | `make l_format_code` | Yes |
| Tests | `make l_test` | Yes |
| Schema | `make l_spectacular` | Yes (if API changed) |
| Migrations | Review migration files | Yes (if models changed) |

### Non-Blocking Checks

| Check | Purpose |
|-------|---------|
| Coverage trend | Coverage should not decrease |
| Test count trend | New features should add tests |
| Doc freshness | Docs should reflect current code |

---

## Test Coverage Requirements

Every new endpoint or modified behavior should have tests covering:

| # | Scenario | Expected | File |
|---|----------|----------|------|
| 1 | Happy path CRUD | 200/201/204 | `test_crud.py` |
| 2 | Unauthenticated | 401 | `test_permission.py` |
| 3 | Authorization (wrong role) | 403 | `test_permission.py` |
| 4 | Inactive member | 403 | `test_permission.py` |
| 5 | Cross-org isolation | 404 | `test_permission.py` |
| 6 | Edge cases | 400/404 | `test_crud.py`, `test_serializer.py` |

### Reference Implementations

- `apps/accounts/tests/test_organization_images/` — 92 tests, clean example
- `apps/accounts/tests/test_stored_files/` — 9 files, extended example
- `apps/accounts/tests/test_organization_profiles/` — 68 tests

---

## Quality Grading

### Per-Domain Quality Score

Each domain (accounts, teams, generics) is graded on:

| Dimension | Weight | Measurement |
|-----------|--------|-------------|
| Test coverage | 40% | `pytest-cov` percentage |
| Test structure | 20% | Follows modular pattern |
| Documentation | 20% | Docs exist and are current |
| Lint compliance | 10% | `ruff check` passes |
| Schema compliance | 10% | `spectacular` passes |

### Grade Scale

| Grade | Coverage | Description |
|-------|----------|-------------|
| A | ≥ 90% | Excellent — production ready |
| B | 80-89% | Good — minor gaps |
| C | 70-79% | Acceptable — needs improvement |
| D | 60-69% | Poor — significant gaps |
| F | < 60% | Failing — must improve before merge |

### Tracking

Quality scores are tracked in `docs/exec-plans/tech-debt-tracker.md` for
domains that fall below target.
