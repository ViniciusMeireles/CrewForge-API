# AGENTS.md

## Purpose

CrewForge is a Django REST API for organization-aware access control.

- **Organizations**, **members**, **invitations**, **teams**, **files**
- Organization context via session (`organization_id`) — JWT alone is NOT enough
- Role hierarchy: Owner > Admin > Manager > Member

See [`docs/product-sense.md`](./docs/product-sense.md) for domain model and design beliefs.

---

## Stack

Python ≥3.14, Django, DRF, django-filter, simplejwt, drf-spectacular,
PostgreSQL, uv, Docker, Gunicorn, Ruff, pytest + factory-boy.

---

## Authentication Flow

1. `POST /api/auth/token/` — authenticate user (JWT)
2. `GET /api/accounts/organizations/` — list orgs
3. `POST /api/accounts/organizations/{id}/login/` — set session context

Agents must NOT assume JWT alone is sufficient.

---

## Documentation Map

| Document | Description |
|----------|-------------|
| [`docs/architecture.md`](./docs/architecture.md) | Layered architecture, naming conventions, code organization |
| [`docs/product-sense.md`](./docs/product-sense.md) | Design beliefs, domain model, non-goals |
| [`docs/security.md`](./docs/security.md) | Auth flow, cookie rules, security invariants |
| [`docs/reliability.md`](./docs/reliability.md) | Error handling, performance, caching, logging |
| [`docs/quality.md`](./docs/quality.md) | Coverage targets, quality gates, debt tracking |
| [`docs/frontend-integration-guide.md`](./docs/frontend-integration-guide.md) | Consuming the API from SPA frontends |
| [`docs/patterns/`](./docs/patterns/) | Design patterns (structural, behavioral, creational, architectural) |
| [`docs/exec-plans/`](./docs/exec-plans/) | Execution plans, tech debt tracker |
| [`docs/design-docs/index.md`](./docs/design-docs/index.md) | Past architectural decisions with rationale |
| [`docs/references/`](./docs/references/) | LLM-friendly library references |
| [`specs/`](./specs/) | Feature specs and plans |
| [`.github/git-commit-instructions.md`](./.github/git-commit-instructions.md) | Commit conventions |

---

## Non-Negotiable Rules

- Do NOT replace organization-context login with JWT-only assumptions.
- Do NOT switch to SQLite; tests and config are built around PostgreSQL.
- Do NOT bypass existing permission classes when adding new actions.
- Do NOT add comments to code unless explicitly asked.
- Follow MRO: `OrganizationScopedViewSetMixin` → `ModelViewSetMixin` → `viewsets.ModelViewSet`.
- Import generics from `apps/generics/`, not from `apps/accounts/`.
- Permission changes are high-impact: always add tests.
- Never commit secrets or put real values in `example.env`.

---

## Definition Of Done

- Code follows existing app boundaries and naming conventions.
- Permissions and organization scoping preserved.
- Tests cover happy path, auth, permissions, inactive, cross-org.
- `make l_format_code` passes.
- `make l_test` passes.
- `make l_spectacular` passes (if API changed).
- Migrations created and reviewed (if models changed).
- [`docs/frontend-integration-guide.md`](./docs/frontend-integration-guide.md) updated (if request/response changed).

---

## Required Checks

```bash
make l_format_code   # ruff check + format
make l_test          # pytest
make l_spectacular   # schema (if API changed)
```

---

## Commit Conventions

Emoji + type prefix. Max 4 words after prefix.

| Type | Emoji | Prefix |
|------|-------|--------|
| Feature | ✨ | `feat` |
| Bug fix | 🐛 | `fix` |
| Docs | 📚 | `docs` |
| Tests | 🧪 | `test` |
| Refactor | ♻️ | `refactor` |
| Chore | 🔧 | `chore` |
| Cleanup | 🧹 | `cleanup` |
| Removal | 🗑️ | `remove` |

Example: `✨ feat: add login page`

See [`.github/git-commit-instructions.md`](./.github/git-commit-instructions.md) for full details.

---

## Agent Skills

| Skill | Purpose |
|-------|---------|
| `scaffold-resource` | Generate complete Django resource (12-step checklist with grilling) |
| `scaffold-permission` | Generate permission class with role-based checks |
| `scaffold-test-matrix` | Generate 8 test files covering 19 scenarios |

Skills are in `.agents/skills/`. Reference templates in `references/` subdirectories.
