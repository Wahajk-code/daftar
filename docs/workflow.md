# Workflow

How the work is run with Claude Code. The build itself is in `build-plan.md`.

## 1. Mode
Claude works autonomously through the passes in order. It does not wait for approval between steps. It stops only for:
- a sensitive command (section 2);
- a gate that fails twice;
- a missing credential or account;
- an ambiguity in the brief that changes the result;
- the design checkpoint in Pass 6, and the end of each pass.

At the end of each pass it writes a short report and waits for the owner to review before the next pass.

## 2. Commands

**Runs without asking:** reading files; editing files in the repo; `docker compose up`, `down` (without `-v`), `logs`,
`ps`; running tests, lint, format checks, type checks and builds in Docker; installing project dependencies named in
`architecture.md` with `uv` or `pnpm`; running migrations and test fixtures against `daftar_test`; read-only git
(`status`, `diff`, `log`, `show`).

**Asks first, every time** (one request per command, then runs it itself once approved):
- `docker compose down -v`, or anything that drops, truncates, recreates or downgrades the **dev** database
- any `git add`, `commit`, `reset`, `clean`, `checkout`, `rebase`, `stash`, or branch change; `git push` is never run
- deleting or moving files outside a few known generated folders (`rm`, `Remove-Item`, `mv`)
- installing anything globally or at system level; changing PATH, permissions or services
- any network call to a deployment or account service (hosting, database, email, storage dashboards or CLIs)
- any command that reads, writes or prints `.env` or any credential; Claude never opens `.env`
- a dependency not named in `architecture.md` (state what it replaces and why)

**Request format**
```
COMMAND:  <exact command>
WHAT:     <what it does>
WHY NOW:  <why this step needs it>
RISK:     <what it changes, and whether it can be undone>
IF WRONG: <what will be visible and what the recovery is>
```

If a command fails, show the exact error. After two failed attempts, stop and report; do not try a third time.

## 3. Decisions
`decisions.md` already answers the open questions with reasons. For a new decision: choose the best option, add a row
(choice, why, strongest objection), and continue. If the owner disagrees, argue the case once with evidence, then follow
the owner's call and update the row.

## 4. Commits
Commits are made in the owner's name. Claude never adds a trailer or attribution line to a message.
- At each checkpoint Claude asks to commit: it shows `git diff --stat`, the proposed message
  (`add: <thing>`, `updated: <thing>` or `fixed: <thing>`, with the story ID in brackets when one applies), and the author from `git config user.name` and `user.email`.
- After approval it runs `git add` and `git commit` itself. It never pushes; there is no remote until the owner adds one.
- Examples: `add: voucher balance trigger (E2)`, `updated: allocation recomputes when the amount changes (C2)`, `fixed: second approval returning 500 instead of 409 (C5)`.
- One commit per coherent step inside a pass, not one commit per pass, so the history reads as the work did.

## 5. Context practice
- Read `CLAUDE.md`, then only the section of `build-plan.md` for the current pass and the parts of the other docs that
  step needs. Do not load the whole docs folder.
- Tick checkboxes in `build-plan.md` as steps finish. The file is the source of truth for progress, so a new session
  can resume from it.
- Output diffs, not whole files. Paste failure output, not whole files. Use a generator for scaffolding
  (`uv init`, `alembic init`, `create-next-app`, `create-expo-app`, `openapi-typescript`).
- Run lint, format and types before tests: cheap failures first.
- Use the review command in a fresh context for cold reviews.

## 6. Model and effort
| Work | Model | Effort |
|---|---|---|
| Architecture, the ledger, allocation, status rules, auth, security review, offline queue | strong | high; plan mode for the ledger and the security review |
| Repeated CRUD, forms, lists, reports, docs | cheap | low |
| A failing test | mid | medium; escalate after two failures |

Record the model and effort for every prompt in `PROMPTS.md` with a one-line reason.

## 7. Accounts and keys the owner provides
| Service | Needed for | Where it goes |
|---|---|---|
| Cloudinary | Receipts, from Pass 3 | `CLOUDINARY_URL` in the owner's `.env` (copy from `.env.example`) |
| Neon, Render, Vercel | Deploy, Pass 8 | The hosts' environment-variable settings |
| Resend and a sending domain | Production email, Pass 8 | The API host's environment settings |
| `BFF_SHARED_SECRET` (a long random string the owner generates) | Trusting the browser's address in rate limits, Pass 2 | The web host and the API host environment settings |
| Expo Go on a phone | Mobile, Pass 9 | The phone |

Claude never reads `.env`. If a key is missing it says which variable and stops.

## 8. Pass report
```
Pass N: <name>
Changed:       <files and line counts>
Tests:         <what ran, what passed, new tests by story ID>
Decisions:     <each decision made, with where it is recorded>
Struggles:     <what was unclear, guessed or took more than one attempt>
Open:          <questions for the owner>
Not done:      <anything incomplete, stated plainly>
Next:          <the next pass>
```
A stub is never reported as finished.

## 9. Records kept
- `PROMPTS.md`: Part A holds the planning prompts; Part B holds the build. Each significant build prompt in order, with model, effort, a one-line reason and the outcome; cost noted per pass. Claude logs every owner prompt, including corrections and answers to questions, and records the model and effort the owner states. The owner states them in the prompt (for example `[model: strong, effort: high]`) so the log is exact.
- `docs/MISTAKES.md`: each real mistake by the agent, how it was caught, why it was wrong and the fix. Entries are written
  when they happen and only when they are real.
- `decisions.md`: the decision log.
- Transcripts from `~/.claude/projects/` (on Windows `%USERPROFILE%\.claude\projects\`), copied into `docs/transcripts/`
  at the end of each session.

## 10. When something goes wrong
- Do not recreate or drop the dev database to recover. Tests use `daftar_test`.
- Do not edit a test to make it pass; find out why it fails.
- Do not widen scope. A stray bug outside the pass goes in `docs/notes.md`.
- A pass that turns out too large is split at a natural boundary and the plan is updated.
