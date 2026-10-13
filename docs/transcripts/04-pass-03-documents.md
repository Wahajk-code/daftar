# Pass 3: expenses, purchases, attachments, approval workflow

The conversation between the owner and Claude Code, text only. Tool output is left out (only the names of the tools used are shown) and secrets, local paths and email addresses are removed. Times are UTC.

---

### Owner, 2026-10-12 19:50 UTC

proceed

### Claude, 2026-10-12 19:50 UTC

Starting Pass 3. The plan says to read the current Cloudinary SDK docs before writing the integration, so I'm doing that first.

### Claude, 2026-10-12 19:50 UTC


_Tools used: WebFetch x1_

### Claude, 2026-10-12 19:50 UTC


_Tools used: WebFetch x1_

### Claude, 2026-10-12 19:50 UTC


_Tools used: WebFetch x1_

### Claude, 2026-10-12 19:50 UTC


_Tools used: WebFetch x1_

### Claude, 2026-10-12 19:50 UTC


_Tools used: WebFetch x1_

### Claude, 2026-10-12 19:50 UTC


_Tools used: WebFetch x1_

### Claude, 2026-10-12 19:50 UTC


_Tools used: WebSearch x1_

### Claude, 2026-10-12 19:52 UTC


_Tools used: AskUserQuestion x1_

### Approval request answered, 2026-10-12 19:52 UTC

**Asked:** Approve this command?

COMMAND:  uv add cloudinary pillow python-multipart   (in a throwaway container against backend/pyproject.toml and uv.lock, then rebuild the backend images)
WHAT:     Adds three runtime packages: cloudinary (the official SDK for the receipt storage the architecture names), Pillow (re-encodes each uploaded image, which is how EXIF and GPS data are removed, and verifies it really is an image), python-multipart (FastAPI cannot accept a file upload without it).
WHY NOW:  Pass 3 builds receipt and document attachments. architecture.md section 12a requires a signature check, E

**Answer:** Your questions have been answered: "Approve this command?

COMMAND:  uv add cloudinary pillow python-multipart   (in a throwaway container against backend/pyproject.toml and uv.lock, then rebuild the backend images)
WHAT:     Adds three runtime packages: cloudinary (the official SDK for the receipt storage the architecture names), Pillow (re-encodes each uploaded image, which is how EXIF and GPS data are removed, and verifies it really is an image), python-multipart (FastAPI cannot accept a file

### Claude, 2026-10-12 19:53 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 19:55 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 19:57 UTC

Packages installed, SDK signatures checked. Building the foundations first: settings, error codes, the purchase-line calculation, image cleaning and the storage interface.

### Claude, 2026-10-12 19:57 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 19:57 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 19:57 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 19:57 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 19:57 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 19:57 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 19:57 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 19:58 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 19:59 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 19:59 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:00 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:01 UTC

Next the data layer for documents: repositories, then the shared workflow engine.

### Claude, 2026-10-12 20:01 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:01 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:02 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:02 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:02 UTC

## Progress report: Pass 3 (Documents), partway

**Done so far (not yet committed)**
- **Cloudinary check:** the docs fetch was only partly readable (a few pages returned 404). I confirmed the real calls by inspecting the installed SDK: authenticated upload, a time-limited private download link, and delete with cache invalidation.
- **Packages:** you approved `cloudinary`, `pillow` and `python-multipart`, and they're installed.
- **Core modules:**
  - **Purchase-line calculation:** each line is rounded once, the header is the exact sum of the lines, and both withholdings come off the payable.
  - **Image cleaning:** the file type comes from its first bytes, never the name. The image is re-encoded so every piece of metadata is dropped, and a SHA-256 of the file as received is kept.
  - **Storage:** one interface with a Cloudinary version and an in-memory version.
- **Database (migration 0004):** the tables for expenses, their allocations, purchases, purchase lines, attachments and the approval history. The database rules:
  - allocations must add up on both sides, checked at commit;
  - a purchase header must equal the sum of its lines;
  - nothing about a document can change once it leaves Draft, including its lines;
  - the history is append-only;
  - a registered vendor means a tax invoice with a number;
  - these tables can't be deleted from.
- The migration applies, reverses and matches the models (38 database tests pass).
- **Workflow engine:** one engine shared by all three document types. It locks the row, checks the `If-Match` version, runs the transition table, and writes the history and audit rows.
- **Not yet written:** the expense, purchase and attachment services, the routes, and the tests, including the trigger-bypass and parallel-approval reviews.

**Ambiguities**
1. **The Cloudinary code can't be proven yet.** It is built from the SDK's real signatures, but nothing has run against a live account. I'll need `CLOUDINARY_URL` to do one live check at the end of the pass, which is a network call to a storage service, so I'll ask first.
2. **Development storage is in memory,** so receipts vanish when the API restarts. Production refuses that setting. Say if you'd rather dev use Cloudinary once the key exists.
3. **Only the author can submit a draft.** That is a service rule, not a row in the transition table.
4. **The SHA-256 is of the original upload,** so the same file uploaded twice matches for duplicate detection.
5. **A purchase line with category "any" fails** with `TAX_RULE_MISSING`, because no "any" income-tax rate is seeded. Lines should be goods, services or contracts.
6. **An edit to a draft purchase re-prices it,** so the rates are re-copied from the current rules.
7. **Changing the amount of a fixed-split expense** requires sending the new fixed amounts too.

I'm fixing one sloppy placeholder I left in the expense schema (the default for `tax_amount`), then continuing with the services.

### Claude, 2026-10-12 20:02 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:03 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:03 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:03 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:04 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:04 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:05 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:05 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:06 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:06 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:06 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:15 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:15 UTC

Now the Pass 3 tests. First the support code: lookups, vendors and image builders.

### Claude, 2026-10-12 20:16 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:16 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:16 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:16 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:18 UTC

Image cleaning, tax maths and storage pass on the first run, including EXIF and GPS removal. Now the expense API tests.

### Claude, 2026-10-12 20:19 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:19 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:20 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:20 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:22 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:22 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:24 UTC

Expense tests all pass (58). Now the purchase tests, covering D1 to D4 and the pricing.

### Claude, 2026-10-12 20:24 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:25 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:26 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:26 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:26 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:27 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:27 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:28 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:29 UTC


_Tools used: Write x1_

### Claude, 2026-10-12 20:29 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:30 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:30 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:31 UTC

Now the plan's required parallel test: two simultaneous approvals give one winner and one 409.

### Claude, 2026-10-12 20:31 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:31 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:33 UTC

Now the Pass 3 review step: break the allocation rule once and show the tests fail. I'll remove the allocation-side trigger from migration 0004 temporarily.

### Claude, 2026-10-12 20:33 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:34 UTC

Eight trigger tests fail without the rule, and the migration is restored. Now the full gate, with timings, to see what is slow.

### Claude, 2026-10-12 20:34 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:38 UTC

No response requested.

### Owner, 2026-10-12 20:38 UTC

proceed

### Claude, 2026-10-12 20:38 UTC

The session restarted mid-gate, so I don't know whether the last full run finished. I'm checking the working tree and re-running it.

### Claude, 2026-10-12 20:38 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:39 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:39 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:39 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:39 UTC

The Pass 3 records are written. The full backend gate is running in the background, and I'll finish the plan ticks, rebuild the dev API container and send the pass report when it completes.

### Claude, 2026-10-12 20:46 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:46 UTC

Only the config tests fail: they build a production configuration without the new storage requirement. 542 other tests pass. Fixing the test helper.

### Claude, 2026-10-12 20:46 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:46 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:47 UTC

Config tests pass. Now rebuilding the dev stack so the API container has the new packages, and checking the new routes appear.

### Claude, 2026-10-12 20:47 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:50 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:50 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:50 UTC

## Pass 3: Documents

All the plan's Pass 3 steps are done and ticked. Nothing is committed yet; the three commit proposals are below.

**Changed**
- **New source:** 12 files, about 3,000 lines. They hold the document models, migration 0004, the purchase-line calculation, image cleaning, storage, the workflow engine, the expense, purchase and attachment services, and their routes.
- **Modified source:** 13 files, +338 / -2. This includes `uv.lock`, `docker-compose.yml`, settings and error codes.
- **Tests:** 7 new files, about 2,400 lines, and 7 modified files, +134 / -5.
- **Docs:** 6 files changed, about +41 / -21.
- **Dev API:** the container is rebuilt and healthy, and it now serves 70 paths, 20 of them for documents.

**Tests**
- Backend gate: ruff, format and mypy strict are clean.
- The last full run had 542 passing and 10 failing. All 10 were config tests that didn't know production now requires Cloudinary. I fixed the test helper and re-ran those 11, which pass. The rest of the suite was unchanged, so I did not run it a second time (a full run takes about 7 minutes).
- By story:

| Story | What the tests cover |
|---|---|
| C1, C2 | Direct and indirect expenses, exact splits, the leftover paisa, type switching, and the preview endpoint reporting a shortfall |
| C3, D6 | Receipts and purchase documents |
| C4, C5, C7 | Submit, approve and reject, reopen |
| D1 to D4 | Server-side pricing, registered and unregistered vendors, same lifecycle |
| F2 | History |
| A3 | 404 for another user's expense on every route |
| A4 | Self-approval for expenses and purchases |

- **Database rules:** 30 tests reach the rules by going around the service.
- **Parallel tests:** three new ones, all with exactly one winner and one 409:
  - two approvals at once
  - an approval against a rejection
  - a double-click on Submit
- **Review step:** with the allocation triggers removed from the migration, 8 database tests fail and the migration is now restored.

**Decisions:** rows 83 to 91 in `docs/decisions.md`: image rules and limits, storage keys, deletable draft rows, author-only rules, locking plus `If-Match`, purchase withholding bases, re-pricing on edit, split recalculation, and `actions` on reads.

**Struggles**
- A zero amount reached the database CHECK and came back as a 500. I added a positive-amount type at the boundary and mapped the document rules to proper errors.
- Deferred triggers read the row as it was when queued, so I made them re-read the current row.
- Setting a type to direct needed the allocation method cleared before the rows were removed.
- A signed-money type was needed for the preview's "remaining".
- Message-matching in tests: Postgres reports the rule in `diag.constraint_name`, not in the message.
- Mistakes M6 (division in the attachment service, the same slip as M4) and M7 (the stale dev container) are logged in `docs/MISTAKES.md`.

**Open**
1. **The Cloudinary code is untested live.** I wrote it from the installed SDK's real signatures, but nothing has run against an account. I need `CLOUDINARY_URL` to do one live upload, fetch and delete. That is a network call to a storage service, so I'll ask first when you're ready.
2. **The seeded tax rates are still unverified.** This matters more now that purchases use them.
3. **`PERIOD_CLOSED` is still 409 versus 422.** Periods start to matter in Pass 4.
4. A purchase line with category "any" is refused until an Admin adds an "any" income-tax rule.

**Not done**
- The expense CSV, the duplicate-detection banner, and the emails on submit, approve and reject belong to Pass 5.
- The upload limit is tested. The per-user export limit has no endpoint until Pass 5.
- `.env.example`, frontend tests and the dev-database migration are still left to the end.
- C6 (post an expense) and D5 (link a purchase to its paying voucher) are Pass 4.

**Next:** Pass 4, the ledger. The plan says to use plan mode for it and to review everything in the pass.

### Claude, 2026-10-12 20:50 UTC


_Tools used: AskUserQuestion x1_

### Approval request answered, 2026-10-12 20:53 UTC

**Asked:** Approve these three commits (author scar3crow0 <<email>>, no trailer, nothing pushed)?

COMMAND 1:  git add backend/app backend/alembic backend/pyproject.toml backend/uv.lock docker-compose.yml  then  git commit -m "add: expenses, purchases, attachments and the approval workflow (C1 to C5, C7, D1 to D4, D6, F2)"
DIFF 1:     12 new source files (about 3,000 lines) and 13 modified (+338 / -2): document models, migration 0004 with its database rules, purchase pricing, image cleaning, storage, the workflow engine, the services and routes, three packages.

COMMAND 2:  git add backend/tests  then  g

**Answer:** Your questions have been answered: "Approve these three commits (author scar3crow0 <<email>>, no trailer, nothing pushed)?

COMMAND 1:  git add backend/app backend/alembic backend/pyproject.toml backend/uv.lock docker-compose.yml  then  git commit -m "add: expenses, purchases, attachments and the approval workflow (C1 to C5, C7, D1 to D4, D6, F2)"
DIFF 1:     12 new source files (about 3,000 lines) and 13 modified (+338 / -2): document models, migration 0004 with its database rules, purchase pri

### Claude, 2026-10-12 20:54 UTC


_Tools used: Bash x1_

### Claude, 2026-10-12 20:54 UTC

Pass 3 is committed as scar3crow0, with no trailer, and nothing was pushed.

| Commit | Message |
|---|---|
| `ce781d4` | add: expenses, purchases, attachments and the approval workflow (C1 to C5, C7, D1 to D4, D6, F2) |
| `86a0abb` | add: Pass 3 tests, database rule tests and parallel approval tests |
| `1a19479` | updated: Pass 3 decisions 83 to 91, mistakes M6 and M7, plan ticks and story matrix |

The working tree is clean apart from the three files I left out on purpose: `START-PROMPT.md`, `docs/skills.md` and `frontend/README.md`. The dev stack is healthy on ports 8001 and 3001.

Before Pass 4, two things need your input:
- **Cloudinary:** when you can, provide `CLOUDINARY_URL` so I can run one live upload, fetch and delete. I'll ask for approval at that point, since it's a call to a storage service.
- **Tax rates:** the seeded rates still need an accountant's confirmation.

Pass 4 is the ledger, and the plan asks for plan mode and a review of everything in the pass. I'll wait for your go before starting it.

### Owner, 2026-10-12 20:54 UTC

proceed

### Claude, 2026-10-12 20:54 UTC

Pass 4 is the ledger, and the plan and workflow doc both call for plan mode on it. I'm loading the plan-mode tools and will research before proposing the design.

### Claude, 2026-10-12 20:54 UTC


_Tools used: ToolSearch x1_

### Claude, 2026-10-12 20:54 UTC


_Tools used: EnterPlanMode x1_
