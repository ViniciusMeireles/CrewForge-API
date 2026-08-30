# CrewForge Documentation

This directory is the **system of record** for all CrewForge knowledge.
Everything an agent needs to reason about the codebase lives here.

> Agents should start with `AGENTS.md` (the table of contents), then follow
> pointers into this directory for deeper context.

---

## Table of Contents

### Core Documentation

| File | Purpose | Audience |
|------|---------|----------|
| [`architecture.md`](./architecture.md) | Layered architecture, naming conventions, code organization, complexity rules | Agents, new engineers |
| [`product-sense.md`](./product-sense.md) | Design beliefs, non-goals, domain model rationale | Agents, product decisions |
| [`security.md`](./security.md) | Auth flow, cookie rules, threat model, invariants | Agents, security review |
| [`reliability.md`](./reliability.md) | Error handling, performance, caching, logging, Sentry | Agents, operations |
| [`quality.md`](./quality.md) | Coverage targets, quality gates, debt tracking | Agents, CI pipeline |

### Guides

| File | Purpose | Audience |
|------|---------|----------|
| [`frontend-integration-guide.md`](./frontend-integration-guide.md) | Consuming the API from SPA frontends | Frontend engineers, agents |

### Design Patterns

| File | Purpose |
|------|---------|
| [`patterns/structural-patterns.md`](./patterns/structural-patterns.md) | Mixin, Abstract Model, Module |
| [`patterns/behavioral-patterns.md`](./patterns/behavioral-patterns.md) | Template Method, Strategy, Validation Chain |
| [`patterns/creational-patterns.md`](./patterns/creational-patterns.md) | Factory Method, Builder |
| [`patterns/architectural-patterns.md`](./patterns/architectural-patterns.md) | Layered Architecture, Facade, Test Infrastructure |
| [`patterns/test-patterns.md`](./patterns/test-patterns.md) | Modular test structure, coverage matrix, assertions |

### Execution Plans

| Path | Purpose |
|------|---------|
| [`exec-plans/TEMPLATE.md`](./exec-plans/TEMPLATE.md) | Template for new execution plans |
| [`exec-plans/active/`](./exec-plans/active/) | Plans currently in progress |
| [`exec-plans/completed/`](./exec-plans/completed/) | Finished plans (historical record) |
| [`exec-plans/tech-debt-tracker.md`](./exec-plans/tech-debt-tracker.md) | Known technical debt, prioritized |

### Design History

| File | Purpose |
|------|---------|
| [`design-docs/index.md`](./design-docs/index.md) | Catalog of past design decisions with rationale |

### Agent References

| File | Purpose |
|------|---------|
| [`references/django-rest-framework-llms.txt`](./references/django-rest-framework-llms.txt) | DRF API summary for LLM consumption |
| [`references/django-filter-llms.txt`](./references/django-filter-llms.txt) | django-filter summary for LLM consumption |
| [`references/simplejwt-llms.txt`](./references/simplejwt-llms.txt) | simplejwt summary for LLM consumption |
| [`references/factory-boy-llms.txt`](./references/factory-boy-llms.txt) | factory-boy summary for LLM consumption |
| [`references/drf-spectacular-llms.txt`](./references/drf-spectacular-llms.txt) | drf-spectacular summary for LLM consumption |
