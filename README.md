# Daftar

Expenses, purchases and vouchers for a small company. Web app, Expo mobile app, one API.

```
backend/    FastAPI, PostgreSQL
frontend/   Next.js web app and its server-side BFF routes
mobile/     Expo (React Native) app
docs/       spec, architecture, decisions, domain rules, build plan, workflow
```

## Run locally (60 seconds)

You need Docker Desktop. Nothing else.

```
cp .env.example .env              # optional: every value has a development default
docker compose up -d --build      # database, API and web app
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed
```

| What | Where |
|---|---|
| Web app | http://localhost:3001 |
| API (interactive docs in development) | http://localhost:8001/docs |
| Database | localhost:5433 |

Sign in with any demonstration account (password `daftar-demo-2026`):

| Email | Role |
|---|---|
| admin@daftar.pk | Admin |
| accounts@daftar.pk | Accountant |
| approver@daftar.pk | Approver |
| staff@daftar.pk | Staff |

To try real receipts and email locally, fill `CLOUDINARY_URL` and `RESEND_API_KEY` in `.env` (the steps are written in
`.env.example`). On a phone on the same Wi-Fi, open `http://<this computer's address>:3001`: the camera button starts an expense
from a photo of a receipt. Installing it as an app needs HTTPS (the deployed site).

## Tests and checks

```
docker compose --profile test run --rm backend-test      # lint, format, types and the 950+ backend tests
docker compose exec frontend pnpm lint
docker compose exec frontend pnpm typecheck
```

Tests use a separate `daftar_test` database and a fake receipt store, so they need no network.

## Deploying

One repository, one folder per service: `backend/` on Render, `frontend/` on Vercel, the database on Neon, receipts on
Cloudinary and email on Resend. The steps and every environment variable are in `docs/deploy.md`.

## Where to look

| File | What it is |
|---|---|
| `docs/spec.md` | The brief line by line, and how each part is handled |
| `docs/deploy.md` | Deploying: Neon, Render, Vercel, Cloudinary, Resend, step by step |
| `docs/architecture.md` | Design, diagrams, data model, security, local and deployed setup |
| `docs/decisions.md` | Every decision with its reasoning and strongest objection |
| `docs/domain-rules.md` | Money, allocation, numbering, vouchers, tax, dates |
| `docs/build-plan.md` | Ten passes as checklists |
| `docs/workflow.md` | How the work is run with Claude Code |
| `docs/story-matrix.md` | Each user story and its evidence |
| `PROMPTS.md`, `docs/MISTAKES.md` | The prompt log and the record of what the AI got wrong |
