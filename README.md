# Daftar

Expenses, purchases and vouchers for a small company. Web app, Expo mobile app, one API.

```
backend/    FastAPI, PostgreSQL
frontend/   Next.js web app and its server-side BFF routes
mobile/     Expo (React Native) app
docs/       spec, architecture, decisions, domain rules, build plan, workflow
```

## Run locally

```
docker compose up -d --build
```

Web `http://localhost:3000` · API docs `http://localhost:8000/docs` · Postgres on `localhost:5433`.
Copy `.env.example` to `.env` and set `CLOUDINARY_URL` for receipt uploads.

```
docker compose --profile test run --rm backend-test
docker compose --profile test run --rm frontend-test
```

Tests use a separate `daftar_test` database and a fake receipt store, so they need no network.

## Where to look

| File | What it is |
|---|---|
| `docs/spec.md` | The brief line by line, and how each part is handled |
| `docs/architecture.md` | Design, diagrams, data model, security, local and deployed setup |
| `docs/decisions.md` | Every decision with its reasoning and strongest objection |
| `docs/domain-rules.md` | Money, allocation, numbering, vouchers, tax, dates |
| `docs/build-plan.md` | Ten passes as checklists |
| `docs/workflow.md` | How the work is run with Claude Code |
| `docs/story-matrix.md` | Each user story and its evidence |
| `PROMPTS.md`, `docs/MISTAKES.md` | The prompt log and the record of what the AI got wrong |
