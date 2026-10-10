# Execution Plan: Internationalization Part B — API (preferred language + email language)

## Table of Contents

- [Status](#status)
- [Context](#context)
- [Goal](#goal)
- [Approach](#approach)
- [Progress Log](#progress-log)
- [Decisions](#decisions)
- [Done Criteria](#done-criteria)

---

## Status

- [ ] Active
- [x] Completed
- [ ] Cancelled

Closed 2026-10-09 after the Frontend Part B delivery was implemented and
manually approved; the API phases below shipped in the working tree.

---

## Context

Part A of `specs/internationalization.md` (monorepo root) — `LocaleMiddleware`
negotiation, `locale/pt_BR` catalog, email `language` plumbing — is implemented
in this working tree (uncommitted). Part B closes the product gap: a persistent
per-user language preference that governs email language.

- PO spec: `specs/internationalization.md` (monorepo root), part B "NEW decisions"
- Backend implementation spec: `specs/internationalization-part-b.md`
- No GitHub issues (explicit spec decision)

---

## Goal

1. `User.preferred_language` (`en` | `pt-br`, non-null, default `en`, backfilled
   by migration) initialized from the negotiated request language at every
   server-side user creation, exposed and editable **only** via
   `GET/PATCH /api/accounts/users/me/`.
2. Email language resolved at enqueue time per the spec table: invitation →
   invitee preference (case-insensitive email match) → inviter request language
   → English; verification/reset/other → recipient preference → request language
   → English.
3. Profile-only exposure proven by tests; every resolution row covered; catalog
   at 0 untranslated / 0 fuzzy; schema regenerated.

---

## Approach

### Phase 1: Model + migration

- [x] `PreferredLanguageChoices` in `apps/accounts/choices.py` (labels native,
      not translated)
- [x] `User.preferred_language` field (`max_length=8`, `default='en'`,
      `verbose_name`/`help_text` wrapped in `gettext_lazy`)
- [x] Migration `0005_*` — single non-null `AddField`, backfill by default;
      reviewed

### Phase 2: Language helper

- [x] `apps/accounts/utils/language.py`: `normalize_language`,
      `current_language`, `resolve_recipient_language`,
      `resolve_invitation_language` (single `email__iexact` query, never raises,
      always returns an explicit `en`/`pt-br`)

### Phase 3: Profile exposure

- [x] `preferred_language` added to `UserProfileSerializer.fields` (writable);
      absent from every other user/member serializer

### Phase 4: Creation-path initialization

- [x] `SignupSerializer.create` — `user_data.setdefault(...)` before
      `_create_user`
- [x] `UserSerializer.create` — `validated_data.setdefault(...)` (covers
      `create-with-invite` and nested member user saves)

### Phase 5: Email language resolution

- [x] `Invitation.send_email` passes `resolve_invitation_language(self.email)`
      (covers create + resend through the single choke point)
- [x] `PasswordResetRequestView` passes `resolve_recipient_language(user)`
- [x] `send_verification_email` captures `resolve_recipient_language(user)`
      before `transaction.on_commit`
- [x] `apps/accounts/tasks.py` / `apps/generics/tasks.py` unchanged

### Phase 6: Tests

- [x] `apps/accounts/tests/test_preferred_language.py` — model default/choices,
      MigrationExecutor backfill test, signup + create-with-invite
      initialization, payload-injection negatives, serializer exposure matrix
- [x] `apps/accounts/tests/test_utils_language.py` — helper fallback chains
- [x] `apps/accounts/tests/test_user_profile/{test_crud,test_serializer,test_permission}.py`
      — GET/PATCH round-trip, validation (invalid/uppercase/null), partial keep,
      401
- [x] `apps/accounts/tests/test_email_i18n.py` — each resolution row (invitee
      preference, case-insensitive, resend re-resolution, no-request English,
      reset preference-over-request, verification preference-over-request);
      update `test_language_is_captured_before_on_commit`

### Phase 7: Catalog + schema + docs

- [x] `make l_makemessages` → translate new msgids → 0 untranslated / 0 fuzzy
      (`msgattrib` gates) → compiled by `make l_test`
- [x] `make l_spectacular` → `schema.yml` diff reviewed (commit-ready)
- [x] `docs/frontend-integration-guide.md` §6 (+ §4.3/§9 pointers)
- [x] Root `docs/deployment.md` email-language sentence corrected (root-owned,
      copied by `sync-docs`)
- [x] `make -C .. sync-docs` at the end of this delivery

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-10-09 | Plan created; implementation started (plan-only round approved first) |
| 2026-10-09 | Phases 1–7 complete. Migration backfill test uses `TransactionTestCase` (Postgres rejects `ALTER TABLE` inside `TestCase` transaction: "pending trigger events" from FKs on `accounts_user`). Tests: 1383 passed sequential + parallel, 94% cov. Catalog 0/0 untranslated/fuzzy. `makemigrations --check` clean. Schema + guide synced. Nothing committed/staged. |
| 2026-10-09 | Frontend Part B implemented and manually approved (user sign-off); plan closed and moved to `completed/` per `docs/maintenance.md` "After completion" |

---

## Decisions

| Decision | Rationale | Alternatives considered |
|----------|-----------|------------------------|
| Choices enum `PreferredLanguageChoices` in `apps/accounts/choices.py` | Project convention (`docs/architecture.md`); labels stay native/untranslated | Inline `choices=[...]` on the model (literal spec snippet) |
| `verbose_name`/`help_text` wrapped in `gettext_lazy` | Model convention; flows into DRF schema description; 2 msgids translated | Bare field per literal spec snippet |
| Initialization in the two user-creation funnels (signup + `UserSerializer.create`) | Signup builds `User(**data)` directly (bypasses serializer `create`); manager/`save()` would be implicit magic and still miss `User(**data)` | `UserManager.create` override (misses signup), model `save` override (too magical) |
| Invitee lookup = any user owning the email, case-insensitive | Spec-literal (language only; `is_active` not mentioned) | Match `Invitation.get_user()` (`is_active=True`) |
| Helper in `apps/accounts/utils/language.py` | Accounts domain (user/invitation/email); `generics` must stay app-agnostic | `apps/generics/utils/` (would need user model) |
| Migration backfill test uses a real `MigrationExecutor` inside `TransactionTestCase` | Proves the spec AC (unapply → re-apply → assert backfill). `TestCase` fails: uncommitted FK trigger events on `accounts_user` block `ALTER TABLE ... DROP COLUMN`; `TransactionTestCase` commits the fixture insert so DDL works | `TestCase` + `Migration.operations` inspection (rejected — flaky/blocked as observed) |
| Accept DRF's built-in invalid-choice detail | Consistent with every other ChoiceField; envelope is localized; hand-adding a non-project msgid to the `.po` is fragile (`makemessages` obsoletes it) | Custom `error_messages['invalid_choice']` on the profile field |
| Email language resolved at enqueue and passed explicitly | Existing pattern (`language` kwarg + `translation.override` in the worker); worker independent of request/thread state | Resolving in the worker (impossible — no request state) |
| `tech-debt-tracker.md`, root `AGENTS.md`, root `CONTEXT.md` untouched | No debt knowingly deferred; root files handled separately | Adding tracker/status/glossary entries |

---

## Done Criteria

- [x] `preferred_language` only exposed by `GET/PATCH /api/accounts/users/me/`
      (proven by exposure tests)
- [x] Every server-side user creation initializes it from the request language;
      payloads cannot set it
- [x] Migration `0005_*` reviewed; existing users backfilled to `en`
- [x] All email resolution rows covered by tests; resolution at enqueue time
- [x] Profile tests: happy path, validation, 401 (self-only endpoint —
      inactive/cross-org dimensions do not apply: `IsAuthenticated`,
      `get_object = request.user`)
- [x] Catalog: 0 untranslated / 0 fuzzy
- [x] Tests pass (`make l_test`, `make l_test_parallel`)
- [x] Lint passes (`make l_format_code`)
- [x] Schema regenerated if API changed (`make l_spectacular`); `makemigrations --check`
- [x] `docs/frontend-integration-guide.md` updated (request/response changed)
- [x] `make -C .. sync-docs` run at the end of the delivery
- [x] No commits / no staging (working-tree delivery, per feature decision)
- [x] Frontend Part B implemented and manually approved (2026-10-09)
