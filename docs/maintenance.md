# Documentation Maintenance

How to maintain, grow, and restructure CrewForge's documentation over time.

---

## Table of Contents

- [The Core Problem](#the-core-problem)
- [Golden Rule](#golden-rule)
- [When to Create a New File](#when-to-create-a-new-file)
- [How to Create a New File](#how-to-create-a-new-file)
- [When to Split an Existing File](#when-to-split-an-existing-file)
- [How to Split a File](#how-to-split-a-file)
- [When to Move Content Out of AGENTS.md](#when-to-move-content-out-of-agentsmd)
- [Cross-References](#cross-references)
- [Design Decisions](#design-decisions)
- [Execution Plans](#execution-plans)
- [LLM Reference Files](#llm-reference-files)
- [Maintenance Checklist](#maintenance-checklist)

---

## The Core Problem

A monolithic documentation file (like the original 607-line `AGENTS.md`) fails in
predictable ways:

1. **Context crowding.** A giant file pushes out task-relevant information. Agents
   (and humans) miss key constraints because they're buried under unrelated detail.
2. **Non-guidance.** When everything is "important," nothing is. Readers
   pattern-match locally instead of navigating intentionally.
3. **Instant rot.** A monolithic manual becomes stale the moment code changes.
   Nobody knows what's still true, so the whole file loses credibility.
4. **Hard to verify.** A single blob doesn't lend itself to mechanical checks,
   so drift is inevitable.

The solution: treat `AGENTS.md` as the **table of contents** and `docs/` as the
**system of record**.

---

## Golden Rule

> **`AGENTS.md` is the map (~100 lines). `docs/` is the encyclopedia.**

`AGENTS.md` should contain:
- What the project is (1 paragraph)
- Stack (1 line)
- Auth flow (3 steps)
- Where to find things (link table)
- Non-negotiable rules (5-10 items)
- Definition of done (checklist)
- Required checks (commands)
- Commit conventions (table)

Everything else lives in `docs/`.

---

## When to Create a New File

Create a new file in `docs/` when **any** of these are true:

| Signal | Example |
|--------|---------|
| An existing file exceeds **200 lines** | `reliability.md` grew to 250 lines with rate limiting content |
| A file covers **3+ unrelated topics** | `reliability.md` has errors, performance, caching, logging, and Sentry |
| A new domain needs its own documentation | Teams feature added → need team-specific patterns |
| Agents keep asking the same question | "How do I add a new resource?" → needs `architecture.md` checklist |
| A decision has long-term consequences | Session-based auth → needs `design-docs/index.md` entry |
| A library needs agent-friendly reference | DRF, django-filter → need `references/*.txt` |

### Anti-signals (do NOT create a new file when)

- The content fits naturally in an existing file (< 200 lines, same topic)
- It's a one-off note (use a comment or PR description instead)
- It duplicates existing content (link to it instead)

---

## How to Create a New File

### Checklist

1. **Choose the right location:**
   - Core docs: `docs/{topic}.md` (e.g., `docs/caching.md`)
   - Patterns: `docs/patterns/{pattern-name}.md`
   - Execution plans: `docs/exec-plans/{plan-name}.md`
   - References: `docs/references/{library}-llms.txt`
   - Design decisions: add entry to `docs/design-docs/index.md`

2. **Include a Table of Contents:**
   ```markdown
   # Title

   ## Table of Contents

   - [Section 1](#section-1)
   - [Section 2](#section-2)

   ---

   ## Section 1
   ```

3. **Update `docs/README.md`:**
   Add a row to the appropriate table with file, purpose, and audience.

4. **Update `AGENTS.md`** (only if critical):
   If the new doc contains rules agents must follow, add a pointer to the
   "Where To Find Things" table.

5. **Cross-reference from related docs:**
   Add a "Related" section at the bottom linking to nearby docs.

---

## When to Split an Existing File

Split a file when **any** of these are true:

| Signal | Action |
|--------|--------|
| File exceeds **200 lines** | Consider splitting by theme |
| A section exceeds **50 lines** and is self-contained | Extract to its own file |
| **3+ distinct themes** have accumulated | Each theme gets its own file |
| Readers skip sections to find what they need | Each section deserves its own file |
| Two features reference the same file for unrelated reasons | Split by feature |

### Example: Splitting `reliability.md`

Before (250 lines, 5 themes):
```
reliability.md
├── Error Handling (30 lines)
├── Error Response Format (30 lines)
├── Performance Guidelines (40 lines)
├── Database Transactions (15 lines)
├── Caching (30 lines)
├── Logging (25 lines)
├── Sentry Integration (25 lines)
└── Rate Limiting (25 lines)
```

After:
```
reliability.md          # Errors + Performance + Transactions (~85 lines)
caching.md              # Cache strategy (new file, ~40 lines)
logging-sentry.md       # Logging + Sentry (new file, ~55 lines)
```

---

## How to Split a File

1. **Create the new file** with a clear title and Table of Contents.
2. **Move the section** from the original file to the new file.
3. **Leave a pointer** in the original file:
   ```markdown
   ## Caching

   > Moved to [`docs/caching.md`](./caching.md).
   ```
4. **Update `docs/README.md`** with the new file entry.
5. **Update cross-references** in other docs that linked to the old location.
   If the old anchor still exists (via the pointer), old links still work.
6. **Update `AGENTS.md`** if the topic is critical enough to warrant a pointer.

---

## When to Move Content Out of AGENTS.md

Move content from `AGENTS.md` to `docs/` when:

| Current content in AGENTS.md | Move to |
|------------------------------|---------|
| Detailed naming conventions | `docs/architecture.md` |
| Full permission hierarchy explanation | `docs/architecture.md` or `docs/security.md` |
| Performance optimization guidelines | `docs/reliability.md` |
| Error handling patterns with examples | `docs/reliability.md` |
| Testing infrastructure details | `docs/patterns/test-patterns.md` |
| Security considerations list | `docs/security.md` |
| Cache configuration details | `docs/reliability.md` |
| Logging standards | `docs/reliability.md` |
| Sentry integration setup | `docs/reliability.md` |

**What stays in AGENTS.md:**
- Rules that agents must never violate (non-negotiable)
- The map of where to find things
- Quick reference tables (commit types, check commands)
- Definition of done

---

## Cross-References

### Format

Always use relative paths:

```markdown
See [`docs/architecture.md`](./architecture.md) for details.
See [`docs/patterns/test-patterns.md`](./patterns/test-patterns.md) for test conventions.
```

### Rules

- **Never hardcode** repository URLs in markdown links.
- **Always use relative paths** from the current file's location.
- **Include the file extension** (`.md`) in the link.
- **Use anchor links** for same-file navigation: `[Section](#section-name)`.
- **Verify links exist** before committing. Broken links erode trust.

### What to link from AGENTS.md

AGENTS.md should link to:
- `docs/architecture.md` — when agents need to know naming or structure
- `docs/product-sense.md` — when agents need domain context
- `docs/security.md` — when agents handle auth or secrets
- `docs/reliability.md` — when agents handle errors or performance
- `docs/patterns/` — when agents implement new patterns
- `specs/` — when agents need feature specifications

---

## Design Decisions

Long-term design decisions are recorded in `docs/design-docs/index.md` using
a lightweight ADR (Architecture Decision Record) format:

```markdown
## Decision Title

**Date:** YYYY-MM-DD

**Context:** Why this decision was needed.

**Decision:** What was chosen.

**Consequences:**
- Positive: ...
- Negative: ...
```

### When to add a decision record

- When a fundamental architectural choice is made (auth model, data strategy)
- When a library is adopted or rejected with clear reasoning
- When a pattern is established that future agents must follow
- When a tradeoff is explicitly made (e.g., soft-delete over hard-delete)

---

## Execution Plans

### Creating a plan

1. Copy `docs/exec-plans/TEMPLATE.md` to `docs/exec-plans/active/{plan-name}.md`
2. Fill in all sections (Context, Goal, Approach, Progress Log, Done Criteria)
3. Reference from the relevant spec in `specs/` if applicable

### During execution

- Update the **Progress Log** with dates and summaries
- Log **Decisions** as they're made (with rationale and alternatives)

### After completion

1. Move the file from `active/` to `completed/`
2. Update status to `[x] Completed`
3. If the plan reveals new tech debt, add it to `tech-debt-tracker.md`

---

## LLM Reference Files

Files in `docs/references/` are optimized for agent consumption. They should be:

- **Concise** — summarize API surfaces, not full documentation
- **Practical** — focus on patterns used in this codebase
- **Dated** — include "Last verified: YYYY-MM-DD" at the top
- **Self-contained** — an agent should be able to use the library from this file alone

### When to create a new reference

- When adding a new library dependency
- When existing documentation for a library is too verbose for agent context
- When a library has non-obvious patterns that agents keep getting wrong

### When to update a reference

- When upgrading a library to a new major version
- When the codebase adopts new patterns from the library
- When "Last verified" date is more than 6 months old

---

## Maintenance Checklist

### When changing code

- [ ] If the change affects API request/response → update `docs/frontend-integration-guide.md`
- [ ] If the change affects permissions → update `docs/security.md`
- [ ] If the change adds a new pattern → add to `docs/patterns/`
- [ ] If the change affects error responses → update `docs/reliability.md`

### When adding a new resource

- [ ] Follow the checklist in `docs/architecture.md` (New Resource Checklist)
- [ ] Add test files following `docs/patterns/test-patterns.md`
- [ ] Update `docs/architecture.md` if new conventions are introduced

### When making a design decision

- [ ] Add entry to `docs/design-docs/index.md`
- [ ] If it's a non-obvious tradeoff, document the rationale

### Periodic review

- [ ] Check that `docs/README.md` matches actual files in `docs/`
- [ ] Verify cross-references still resolve
- [ ] Review `docs/exec-plans/tech-debt-tracker.md` for stale items
- [ ] Update "Last verified" dates in `docs/references/*.txt` if libraries were upgraded
