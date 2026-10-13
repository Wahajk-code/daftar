# Daftar

Expenses, purchases and vouchers for a small company. A FastAPI API, a PostgreSQL database and a Next.js web app that works on a
desktop and installs on a phone (PWA) with camera capture for receipts.

**Live:** web https://daftar-mauve.vercel.app · API https://daftar-v5us.onrender.com/health

```
backend/    FastAPI, SQLAlchemy, Alembic, PostgreSQL
frontend/   Next.js web app and its server-side BFF
docs/       spec, architecture, ERD, process flow, UI flow, API list, decisions, security, deploy, transcripts
```

## Run locally (60 seconds)

You need Docker Desktop and nothing else.

```
cp .env.example .env              # optional: every value has a development default
docker compose up -d --build      # database, API and web app
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed
```

| What | Where |
|---|---|
| Web app | http://localhost:3001 |
| API and its docs (development only) | http://localhost:8001/docs |
| Database | localhost:5433 |

Sign in with any demonstration account (password `daftar-demo-2026`):

| Email | Role | Can |
|---|---|---|
| admin@daftar.pk | Admin | Everything, plus users, roles, periods and the audit log |
| accounts@daftar.pk | Accountant | Master data, purchases, vouchers, posting and voiding |
| approver@daftar.pk | Approver | Reads submitted documents and approves or rejects them |
| staff@daftar.pk | Staff | Writes and sends their own expenses with receipts |

Real receipts and email locally: fill `CLOUDINARY_URL`, and `SMTP_USER` and `SMTP_PASS` for a Google account, in `.env`
(the steps are in `.env.example`). `docker compose exec backend python -m app.mail_check you@example.com` sends one test message.

On a phone on the same Wi-Fi open `http://<this computer's address>:3001`: a camera button starts an expense from a photo of a
receipt. Installing it as an app needs HTTPS, so use the deployed site.

## Checks

```
docker compose --profile test run --rm backend-test      # lint, format, types and about 960 backend tests
docker compose exec frontend pnpm lint
docker compose exec frontend pnpm typecheck
```

Tests use their own database and a fake receipt store, so they need no network. The two tests the brief names are
`backend/tests/db/test_ledger_rules.py` (voucher balancing) and `backend/tests/unit/test_transitions.py` (status transitions).

## Deploying

One repository, one folder per service: `backend/` on Render, `frontend/` on Vercel, the database on Neon, receipts on
Cloudinary and email over Google SMTP. Steps and every variable are in `docs/deploy.md`.

## Where to look

| File | What it is |
|---|---|
| `docs/spec.md` | The brief, line by line, and where each part is |
| `docs/architecture.md` | The design in one page |
| `docs/erd.md`, `docs/process-flow.md`, `docs/ui-flow.md`, `docs/api.md` | Data model, flows, screens, API list |
| `docs/domain-rules.md` | Money, allocation, numbering, vouchers, tax, dates |
| `docs/decisions.md` | Every decision with its reasoning and strongest objection |
| `docs/security.md` | Controls, checks and known limits |
| `docs/deploy.md` | Deploying and checking the live site |
| `docs/stories.md`, `docs/story-matrix.md` | User stories and the evidence for each |
| `PROMPTS.md`, `docs/MISTAKES.md`, `docs/transcripts/` | The prompt log, what the AI got wrong, the sessions and token usage |
| `CLAUDE.md`, `docs/workflow.md` | How Claude Code was instructed and how the work was run |
