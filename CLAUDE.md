# Daftar

Expense, purchase and voucher manager. `backend/` (FastAPI), `frontend/` (Next.js), `mobile/` (Expo).
Docs: `docs/architecture.md`, `docs/decisions.md`, `docs/domain-rules.md`, `docs/build-plan.md`, `docs/workflow.md`.

## How to work
- Work autonomously through the passes in `docs/build-plan.md`, in order. Read only the current pass and the parts of
  other docs a step needs. Tick checkboxes as steps finish.
- Order is fixed: backend, web app, owner QA, Expo app.
- Stop only for: a sensitive command, a gate failing twice, a missing credential, a material ambiguity, the design
  checkpoint, or the end of a pass. Then write the pass report (format in `docs/workflow.md`).
- Decisions: use `docs/decisions.md`. For a new one, choose the best option, add a row with the reasoning and the
  strongest objection, continue. If I disagree, argue once with evidence, then follow my call.
- Commit messages: `add: <thing>`, `updated: <thing>` or `fixed: <thing>`, story ID in brackets when one applies, no trailer.
- Append one row per significant prompt to Part B of `PROMPTS.md`. Add to `docs/MISTAKES.md` only for a real mistake.

## Commands
Everything runs through Docker Compose. These run without asking: `docker compose up -d --build`, `docker compose down`,
`docker compose logs`, `docker compose ps`, test, lint, format and type commands in containers, project dependency
installs named in `docs/architecture.md`, migrations and fixtures on `daftar_test`, read-only git.

Ask first, one command at a time, in the request format from `docs/workflow.md`, then run it yourself once approved:
`docker compose down -v` or anything that drops, recreates or downgrades the dev database; any `git add`, `commit`,
`reset`, `clean`, `checkout`; deleting or moving files; global or system installs; network calls to hosting, database,
email or storage services; anything touching `.env` or credentials (never open `.env`); a dependency not in the
architecture doc. Never run `git push`.

Gate order: ruff check, ruff format --check, mypy, then tests. Full suite after any migration. If a gate fails twice,
stop and show me. Tests use `daftar_test` only.

## Rules
- Money: `Decimal` and `NUMERIC(14,2)`, never float. Percentages are integer basis points. Division only in `core/money.py`
  and `core/allocation.py`.
- Layers: router (HTTP only) -> service (rules, transactions, ownership) -> repository -> model. Routers never import
  models. Services never import FastAPI.
- Status changes only through `core/transitions.py`. Errors only as a `DomainError` with a code from one enum.
- Separate Create, Update and Read schemas. Reject unknown fields.
- Rate limits are named policies in `core/rate_limit.py` (`docs/architecture.md` section 9a): key on email or user first, count before
  the password check, throttle never lock, answer 429 with `Retry-After`, trust a client address only with the BFF secret, run one API worker.
- Nothing is deleted: master data deactivates, posted data is reversed.
- Time: UTC in storage, the API, logs and exports; timezone-aware datetimes only; the server stamps every instant. On screen use the
  `DISPLAY_TIMEZONE` from `/me`, never the device's zone, with identical formats on web and mobile. `document_date` is a plain date,
  never converted through a timezone. See `docs/domain-rules.md` section 7.
- The database holds every rule it can (deferred balance trigger, unique numbering, one reversal, allocation sums). Each
  needs a test that reaches it by bypassing the service, using `SET CONSTRAINTS ALL IMMEDIATE`.
- Voucher numbers: counter row, `UPDATE ... RETURNING`, at Post only. Never a sequence.
- Lists: `limit` and `offset` with a total count, page size clamped to 100, whitelisted sorts.
- Send email only after commit, as a background task; a provider failure is logged, never raised. Write audit rows in the same transaction as the change. No server-side cache and no queue.
- A lock or idempotency feature needs a real parallel test. After a lost race, re-read with `populate_existing`.
- Receipts go to Cloudinary as authenticated assets and are served only through the API. Tests use the in-memory fake.
  Check current SDK documentation (Cloudinary, Expo) before using an API from memory.
- Roles: one per user; the charter is in `docs/decisions.md` section 4. Only Admins invite, change roles, deactivate and trigger
  resets, and never see or set a password. Nobody approves a document they created.
- Public screens are only login, forgot password, reset password and accept invite, in one 50/50 split layout. No landing, SEO or
  legal pages. Every route is `noindex`. The onboarding tour is skippable at every step and its state is saved on the server.
- Frontend and mobile: types from `backend/openapi.json`; TanStack Query; colours only through tokens; every mutation has a
  pending state, a disabled button and a toast on success and failure; never optimistic for post, void or approve.
  Apply the `daftar-ui` skill.

## Never
floats for money | logic in routers | `.status =` | tokens in localStorage | an interface with one
implementation (the storage interface has two) | TODO or stub in committed code | tests asserting mock calls | emoji
anywhere | unrequested dependencies | work outside the current pass.
