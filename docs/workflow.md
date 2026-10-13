# Workflow

How the work was run with Claude Code.

## Mode

Claude worked through the passes in `build-plan.md` in order, without waiting for approval between steps. It stopped only for a
sensitive command, a gate failing twice, a missing credential, an ambiguity that changes the result, or the end of a pass, and
then wrote a short report (below) for the owner to review.

## Commands

**Ran without asking:** reading and editing repo files; `docker compose up`, `down`, `logs`, `ps`; tests, lint, format, type
checks and builds in Docker; installing the project's own dependencies; migrations on the test database; read-only git.

**Asked first, one request per command:** `docker compose down -v` or anything that drops the dev database; any `git add`,
`commit`, `reset`, `clean`, `checkout`; `git push` (never run by Claude without a direct request); deleting or moving files;
global installs; any call to a hosting, database, email or storage service; anything touching `.env` or credentials (Claude never
opens `.env`); a dependency not named in the architecture.

```
COMMAND:  <exact command>
WHAT:     <what it does>
WHY NOW:  <why this step needs it>
RISK:     <what it changes and whether it can be undone>
IF WRONG: <what will be visible and the recovery>
```

After two failed attempts at a command Claude stops and reports.

## Decisions and commits

- A new decision gets a row in `decisions.md` (choice, why, strongest objection). If the owner disagrees, Claude argues once with
  evidence and then follows the owner's call.
- Commits are in the owner's name with no trailer: `add:`, `updated:` or `fixed:` plus the story ID. Each is shown to the owner
  and approved first; usually three per pass (code, tests, docs and records).

## Practice

- Read `CLAUDE.md`, then only the current pass and the docs a step needs. Tick `build-plan.md` as steps finish, so a new session
  can resume from it.
- Lint, format and types run before tests. A database rule gets a test that bypasses the service. A lock or idempotency feature
  gets a real parallel test.
- Use a stronger model and more effort for the ledger, allocation, status rules, auth and security; a cheaper one for repeated
  CRUD, forms and docs.

## Records

| Record | What it holds |
|---|---|
| `PROMPTS.md` | Every significant prompt in order, with model and effort where stated |
| `docs/MISTAKES.md` | What the AI got wrong, how it was caught, the fix |
| `docs/decisions.md` | The decision log |
| `docs/transcripts/` | The sessions as readable text, with token usage |

## Pass report

```
Pass N: <name>
Changed:   <files and line counts>
Tests:     <what ran and passed, new tests by story ID>
Decisions: <each, with where it is recorded>
Struggles: <what was unclear, guessed or took more than one attempt>
Open:      <questions for the owner>
Not done:  <anything incomplete, stated plainly>
```
