# Pass 4: vouchers, ledger rules, numbering, posting, void, generation

The conversation between the owner and Claude Code, text only. Tool output is left out (only the names of the tools used are shown) and secrets, local paths and email addresses are removed. Times are UTC.

---

### Claude, 2026-10-12 20:56 UTC


_Tools used: AskUserQuestion x1_

### Approval request answered, 2026-10-12 20:56 UTC

**Asked:** Generating a payment voucher from a purchase needs an expense account to debit, but a purchase has no expense category (its lines carry only the tax category: goods, services or contracts). Where should the category come from?

**Answer:** Your questions have been answered: "Generating a payment voucher from a purchase needs an expense account to debit, but a purchase has no expense category (its lines carry only the tax category: goods, services or contracts). Where should the category come from?"="Chosen when generating (Recommended)". You can now continue with these answers in mind.

### Claude, 2026-10-12 20:57 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:57 UTC


_Tools used: ExitPlanMode x1_

### Claude, 2026-10-12 20:57 UTC

The plan is approved. Starting with the pure core: enums, numbering, the ledger maths, and the new error codes and setting.

### Claude, 2026-10-12 20:58 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:58 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:58 UTC

Nothing was written (bash rejected the whole command). I'll use the file tools for the new modules and small scripts for the edits.

### Claude, 2026-10-12 20:58 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:58 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:58 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:59 UTC

Now the voucher models and migration 0005 (tables, the deferred balance trigger, freezes, and the seeded chart).

### Claude, 2026-10-12 20:59 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:59 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:00 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 21:00 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:00 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:01 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:02 UTC

The Docker engine isn't answering. I'll keep writing code that doesn't need it and check back.

### Claude, 2026-10-12 21:02 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 21:03 UTC

While Docker recovers, I'm writing the voucher layer. First the engine changes the voucher guards need: balance, period and reversal facts, and post/void actions.

### Claude, 2026-10-12 21:03 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:03 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:04 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 21:04 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:04 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 21:04 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:04 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:04 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:04 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:04 UTC

Now the voucher service: create and edit, the shared moves, post, void and generation.

### Claude, 2026-10-12 21:05 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 21:05 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:06 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 21:06 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:06 UTC

I can't run anything right now: Docker Desktop reports "unable to start", and the engine has been refusing connections for several minutes. I need you to restart it. Restarting it is a system-level action, so I haven't tried it myself.

**Pass 4 progress so far (written, not yet run):**
- **Plan:** approved. Purchase category and payment method are chosen when the voucher is generated.
- **Core:** voucher numbering (calendar and fiscal year), the ledger maths (balance, offsetting line, reversal, expense and purchase line builders), the new error codes, and a function that gives a reversal its Posted status.
- **Database (migration 0005):**
  - vouchers, voucher lines and number counters;
  - the deferred debit-equals-credit trigger;
  - a parent-account-only-postable rule on lines;
  - freezes on lines and on the voucher header after Draft;
  - unique indexes behind "one reversal per voucher", "generate once" and the two idempotency keys;
  - the 19-account starting chart, default posting accounts and six categories.
- **Service layer:** the voucher repository and service (create, edit, balance check, shared moves, post, void, generate), the schemas, the routes and the `Idempotency-Key` dependency. Expenses and purchases now carry their voucher for D5.

**Still to do once Docker is back:**
- Run the gate and fix whatever the first run turns up. Nothing in Pass 4 has been compiled or tested yet, so expect some fixes.
- Write the Pass 4 tests: E1 to E6, C6, D5, the database bypass tests, the access-matrix extension, and the parallel numbering, replay and void tests, repeated eight times.
- Do the review step: make the balance trigger non-deferred, show the tests fail, then restore it.
- Write the pass report with the explanation of the deferred trigger and why a sequence can't number vouchers, then commit.

**To resume:** restart Docker Desktop, confirm `docker info` works, and tell me to proceed.

### Owner, 2026-10-12 21:07 UTC

working on retstarting docker

### Claude, 2026-10-12 21:07 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:09 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:09 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:10 UTC

Docker is back and the data volume is intact. Fixing the lint and type findings in the new code.

### Claude, 2026-10-12 21:10 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:11 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:11 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:11 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:12 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:13 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:13 UTC

Status: fixing a constraint-name clash found by migration 0005, then re-running. Shortening the last two docstring lines too.

### Claude, 2026-10-12 21:13 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:15 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:20 UTC

The baseline is green (533 passing). Now the Pass 4 tests, starting with shared support: a small ledger of accounts and posting accounts.

### Claude, 2026-10-12 21:20 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:21 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 21:21 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:21 UTC

Core ledger maths passes. Now the main voucher API tests: creating, balance, numbering, posting, idempotency and void.

### Claude, 2026-10-12 21:22 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 21:22 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:24 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:25 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:27 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:28 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:29 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:29 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:31 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:32 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:34 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:36 UTC

Voucher core tests pass. Now generation (E4), posting a source (C6), the two-way link (D5), and the fresh-install check.

### Claude, 2026-10-12 21:37 UTC


_Tools used: Write x1_

### Owner, 2026-10-12 21:38 UTC

(context summary written by the tool when the conversation was compacted; omitted)

### Claude, 2026-10-12 21:38 UTC

I wrote that file against helper names I haven't verified, so I'll check them against the support module and run it.

### Claude, 2026-10-12 21:38 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 21:38 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 21:38 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 21:38 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 21:38 UTC

The helpers exist. Running the new file.

### Claude, 2026-10-12 21:38 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:39 UTC

The failure is a mistake in my test. `indirect_expense` defaults to `bank_transfer`, so the credit correctly went to 1200. I'll fix the test and fix the over-long docstring line, then rerun.

### Claude, 2026-10-12 21:39 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:40 UTC

Posting accounts are never deleted (a database rule), so those two tests must build a ledger without the key instead. I'll add a `skip` option to `create_ledger`.

### Claude, 2026-10-12 21:40 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:41 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:41 UTC

## Progress report

### Done and committed (Passes 1 to 3, last commit `1a19479`)
- **Pass 1 (foundation):** auth, users, invites, tokens, audit, rate limits, the money and allocation core, the transition table, and the migrations.
- **Pass 2 (master data):** vendors, the chart of accounts, categories, cost centres and projects, posting accounts, periods, and the seeded tax rules.
- **Pass 3 (documents):** expenses and purchases with the shared workflow, optimistic locking, attachments (Cloudinary-style storage with a memory fake), and the access matrix and parallel tests.

### Pass 4 (ledger), uncommitted
Working now:
- **Migration 0005:** vouchers, lines and number counters, with every database rule I could put there. That means the deferred balance trigger, freeze and no-delete triggers, the postable-account check, and unique numbers, keys and reversals. It also seeds the 19-account chart, the default posting accounts and six categories.
- **Core:** numbering (calendar or fiscal year) and the ledger builders (balance, offsetting line, reversal, expense and purchase lines).
- **Services and routes:** create, edit, submit, approve, reject, reopen, post, void, history, the balance check, and generate-from-expense and generate-from-purchase.
- **Post and void:** both take an idempotency key and run in one transaction. Post also posts the source document.
- **Tests passing so far:**
  - 23 unit tests.
  - 46 voucher API tests.
  - The DB tests.
  - 22 new generation, source-posting and link tests, which I just finished (E4, C6, D5).
- The gates (ruff, format and mypy) are clean.

Still to do in Pass 4:
1. A DB-level ledger rules test that bypasses the service, using `SET CONSTRAINTS ALL IMMEDIATE`.
2. `voucher_id` added to the access-matrix path parameters.
3. Parallel tests, repeated 8 times: N simultaneous posts, a replayed key, and simultaneous voids.
4. A fresh-install seed test in a scratch database.
5. The review mutation: make the balance trigger non-deferred, show the tests fail, then restore it.
6. The full gate, a dev stack rebuild, and the records (decisions, mistakes, plan and story ticks, PROMPTS row).
7. The pass report, then the commit proposal.

### Mistakes I made this stretch (to be logged in MISTAKES.md)
- A query after assigning `updated_at` stepped the version early (the autoflush hazard I already knew about).
- Self-referencing relationships refreshed the original voucher during a void.
- I dropped unset defaults when dumping a PATCH body.
- I added a no-delete trigger on voucher lines that blocked my own line replacement.
- I wrote a test assuming the wrong default payment method, and two tests that deleted posting accounts, which the database rightly forbids.

### Ambiguities
Nothing blocks me. These are the judgement calls I made, so tell me if you disagree with any:
1. **Voiding a voucher does not reopen its expense or purchase.** It stays Posted and the books carry the reversal (decision 33). There is currently no way to generate a replacement voucher for it.
2. **Seeded chart and categories.** They come from `seed-data.md` and are marked unverified, like the tax rates. An accountant should confirm them before real use.
3. **Fiscal year start.** I assumed July, named by the year it ends in, with calendar mode as the default. This is the only part of numbering that depends on Pakistan's fiscal year.
4. **Dev database.** It still needs the single migration run you deferred to the end (0001 to 0005).

I'm continuing with the DB-level ledger rules test next.

### Owner, 2026-10-12 21:54 UTC

proceed

### Claude, 2026-10-12 21:54 UTC


_Tools used: Glob x1_

### Claude, 2026-10-12 21:54 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 21:54 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 21:54 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 21:54 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 21:54 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 21:54 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 21:54 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 21:54 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 21:54 UTC

Writing the database-level ledger rules test now: every voucher rule reached by going around the service.

### Claude, 2026-10-12 21:55 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 21:55 UTC

I'll tidy the clumsy helper, then run the file.

### Claude, 2026-10-12 21:55 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:55 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 21:56 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:56 UTC

All 45 DB-level tests pass. Next is the access matrix, which needs `voucher_id`.

### Claude, 2026-10-12 21:56 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 21:56 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 21:56 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 21:57 UTC

The access matrix passes. Next are the parallel tests. I'll check how the existing ones are built.

### Claude, 2026-10-12 21:57 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 21:57 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 21:57 UTC

The scratch database already holds the seeded chart, so the parallel tests can use it directly. Writing them now.

### Claude, 2026-10-12 21:58 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 21:58 UTC

I need to check the column names and response shape those tests assume.

### Claude, 2026-10-12 21:58 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 21:58 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 21:58 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:00 UTC

All six pass, including the replay race. Fixing the lint and mypy items.

### Claude, 2026-10-12 22:00 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:00 UTC

Now the fresh-install seed test. I'll check what the migration seeds.

### Claude, 2026-10-12 22:00 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 22:00 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 22:00 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 22:01 UTC

That inline helper is clumsy. I'll move it to a proper module-level function that uses `world.run`.

### Claude, 2026-10-12 22:01 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:01 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:02 UTC

Now the review mutation. I'll make the balance trigger fire immediately instead of at commit, show the tests fail, then restore the migration.

### Claude, 2026-10-12 22:02 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:03 UTC

Thirty tests fail with the non-deferred trigger, and the line-replacement edit through the API breaks too. Restoring the migration now.

### Claude, 2026-10-12 22:03 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:04 UTC

Restored and clean. Now the full gate.

### Claude, 2026-10-12 22:04 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:14 UTC

The full gate is running in the background, and a second test run against `daftar_test` would collide with it. So I'll do the records meanwhile.

### Claude, 2026-10-12 22:14 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 22:14 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 22:14 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 22:14 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 22:14 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 22:14 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 22:14 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 22:14 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:16 UTC

The Pass 3 parallel tests are fixed. Now the eight repeats of the Pass 4 parallel tests, in the background.

### Claude, 2026-10-12 22:16 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:17 UTC

While that runs I'll do the records. First I'll check what `architecture.md` says about `PERIOD_CLOSED`.

### Claude, 2026-10-12 22:17 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 22:17 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 22:17 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 22:17 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 22:17 UTC

`architecture.md` line 142 still says a closed period is a 422. I'll correct it.

### Claude, 2026-10-12 22:17 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 22:17 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:17 UTC

Now the mistakes log.

### Claude, 2026-10-12 22:17 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:17 UTC

Now the PROMPTS rows. I'll check the table's end first.

### Claude, 2026-10-12 22:17 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 22:17 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:17 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 22:17 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 22:18 UTC

I've seen these tests pass, so I'll tick the backend column for E1 to E6, D5 and C6, and the Pass 4 plan steps for which I've seen the evidence.

### Claude, 2026-10-12 22:18 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:18 UTC

While the repeat runs go, I'll check whether rebuilding the dev stack would migrate the dev database, which you asked to defer.

### Claude, 2026-10-12 22:18 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 22:18 UTC

Nothing in the dev stack migrates automatically, so a rebuild is safe. I'll do it after the repeat runs finish, to keep their timing clean.

### Claude, 2026-10-12 22:18 UTC


_Tools used: Monitor x1_

### Claude, 2026-10-12 22:18 UTC


_Tools used: Monitor x1_

### Claude, 2026-10-12 22:18 UTC

That stray call was a mistake and the watch is already running. While it waits I'll read the pass-report format.

### Claude, 2026-10-12 22:18 UTC


_Tools used: Grep x1_

### Claude, 2026-10-12 22:18 UTC

Meanwhile, the line counts for the report, using read-only git.

### Claude, 2026-10-12 22:18 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:18 UTC

Everything is staged for the report. Now I'm waiting on the repeat runs.

### Claude, 2026-10-12 22:18 UTC


_Tools used: Read x1_

### Claude, 2026-10-12 22:18 UTC


_Tools used: ScheduleWakeup x1_

### Claude, 2026-10-12 22:18 UTC

The eight repeat runs of the parallel ledger tests are still going. Everything else for Pass 4 is written and passing in targeted runs. Still to do:

- **Repeat runs:** confirm all eight pass.
- **Full suite:** rerun it after the `create_lookups` fix. The previous full run had 3 failures, all in Pass 3 parallel tests that collided with the seeded chart. Those 12 tests now pass.
- **Dev stack:** rebuild it and check `docker compose ps`.
- **Pass report:** write it, then ask you for commit approval.

### Owner, 2026-10-12 22:26 UTC

proceed

### Claude, 2026-10-12 22:26 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:26 UTC

Five of eight runs have passed, 6 of 6 each time. I'll wait for the last three before touching anything that could affect them.

### Claude, 2026-10-12 22:26 UTC


_Tools used: ScheduleWakeup x1_

### Claude, 2026-10-12 22:26 UTC

Runs 6 to 8 are still going, about five more minutes. After that I'll run the full suite, rebuild the dev stack, and write the pass report.

### Claude, 2026-10-12 22:31 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:31 UTC

All eight runs passed, 6 of 6 each time. Next I'll reflow the two long migration lines (formatting only), then run the full gate.

### Claude, 2026-10-12 22:31 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:31 UTC

The full gate is running (about 10 minutes). When it finishes I'll rebuild the dev stack and write the pass report.

### Claude, 2026-10-12 22:31 UTC

That monitor was only the watcher for the eight repeat runs, which already finished. The full gate is still running, so I'm waiting on it.

### Claude, 2026-10-12 22:31 UTC


_Tools used: ScheduleWakeup x1_

### Claude, 2026-10-12 22:31 UTC

Waiting for the full gate to finish.

### Claude, 2026-10-12 22:41 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:41 UTC

The full gate passed: ruff, format, mypy and 697 tests. One migration line is 122 characters; ruff skips that folder, but I'll tidy it, then rebuild the dev stack.

### Claude, 2026-10-12 22:41 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:41 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:44 UTC

The stack is healthy. A quick check that the new routes are served:

### Claude, 2026-10-12 22:44 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:44 UTC

Last record updates: tick the remaining plan items and add the pass-4 evidence.

### Claude, 2026-10-12 22:44 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:44 UTC

## Pass 4: Ledger, report

Vouchers, numbering, post, void and generation are built and tested, and the full gate passes. Nothing is committed.

**Changed** (24 files modified, 12 new):
- **Migration:** `0005_vouchers.py` (about 410 lines).
- **Core:** `core/ledger.py` (164), `core/numbering.py` (25), plus edits to `transitions.py`, `errors.py` and `enums.py`.
- **Models, repository, schemas, service, router:** vouchers.py in each (171, 116, 127, 593 and 160 lines). `routers/documents.py` gained the two generate routes. `services/workflow.py` gained the post and void actions.
- **Tests:** 7 new files, about 2,175 lines.
- **Records:** `decisions.md`, `MISTAKES.md`, `PROMPTS.md`, `story-matrix.md`, `build-plan.md`, `architecture.md`.

**Tests:**
- **Gate:** ruff, format, mypy and the full suite (697 tests) pass.
- **New tests:**
  - E1 to E5: 23 unit tests and 46 voucher API tests.
  - E4, C6, D5: 22 generation tests.
  - Database rules: 45 tests that go around the service using `SET CONSTRAINTS ALL IMMEDIATE`.
  - E3, E5, E6: 6 parallel tests.
  - E4: 2 fresh-install tests.
  - A3: the access matrix now covers the 12 voucher routes.
- **Eight repeats:** the parallel ledger tests passed 6 of 6 on each of 8 consecutive runs.
- **Review mutation:** with the balance trigger made non-deferred, 30 tests failed. One was the API line-replacement edit; the rest were database tests. I restored the trigger and all pass again.
- **Dev stack:** rebuilt and healthy. It serves 82 paths, including 12 voucher routes. The dev database is not migrated, as you asked.

**Why the balance trigger is deferred:** a voucher's lines arrive one at a time, and the first line alone is always out of balance. A trigger that fires after each row would reject every voucher. The deferred trigger waits for commit and then reads the lines as they stand, so any route that ends unbalanced is refused. Editing a draft by deleting and re-inserting lines is also safe, which the mutation showed.

**Why a sequence cannot number vouchers:** a Postgres sequence is not rolled back. A post that fails after taking a number leaves a permanent gap. `test_e3_a_failed_transaction_gives_its_number_back_but_a_sequence_would_not` demonstrates this. The counter row is incremented inside the posting transaction, so a rollback gives the number back. The row lock also makes posts queue instead of colliding.

**Decisions:** rows 92 to 102 in `decisions.md`, including the `architecture.md` correction that a closed period is a 409.

**Struggles** (mistakes M8 to M13 in `MISTAKES.md`):
- A query after an assignment stepped the version early.
- Self-referencing relationships refreshed the voucher being voided.
- I added a no-delete trigger on voucher lines that blocked my own edit path.
- The seeded chart collided with existing tests. Only the full run exposed the Pass 3 parallel ones.
- A PATCH dropped unset fields.
- Some tests were written against assumptions I hadn't checked.

**Open for you:**
1. The seeded chart, categories and posting accounts are unverified; an accountant should confirm them.
2. The fiscal year start (July, named by the year it ends in) is my assumption for Pakistan; calendar mode is the default.
3. Voiding a voucher leaves its expense or purchase Posted (decision 33), and there is no flow yet to issue a replacement.
4. Void is Admin only (decision 97). Is that right, or should accountants be able to void?

**Not done:**
- **Cloudinary live check:** still needs `CLOUDINARY_URL`.
- **Dev database:** still needs the single migration run (0001 to 0005).
- **Deferred to the end, as you asked:** `.env.example` and the frontend tests.

**Next:** Pass 5, backend completion (emails, CSV reports, duplicate warnings, seeds, openapi export), once you say go.

**Proposed commits**, for your approval. Authored as scar3crow0 <<email>>, with no trailer:
1. `add: vouchers, ledger rules, numbering, post, void and generation (E1-E6, D5, C6)`: migration 0005, `app/` changes, and `alembic` changes.
2. `add: tests for the ledger (E1-E6, D5, C6)`: all `backend/tests/` changes.
3. `updated: records for Pass 4`: `PROMPTS.md`, `docs/` files.

I will leave out `START-PROMPT.md`, `docs/skills.md` and `frontend/README.md`, as for the earlier commits. Shall I run these?

### Owner, 2026-10-12 22:44 UTC

proceed

### Claude, 2026-10-12 22:44 UTC

I'll run the commits one at a time, starting with a check of the git identity.

### Claude, 2026-10-12 22:44 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:44 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 22:44 UTC


_Tools used: Bash x1_
