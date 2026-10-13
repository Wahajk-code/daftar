# Decisions

Every decision is answered. Each has the reasoning and the strongest objection, so a change can be argued
on the merits. To change one, edit the row and note the date and reason.

**Protocol for a new decision.** Choose the best option, add a row here (choice, why, strongest objection),
and continue. If the owner disagrees, argue the case once with evidence, then follow their call.

## 1. Stack and structure

| # | Decision | Why | Strongest objection |
|---|---|---|---|
| 1 | Backend: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 | Native `Decimal` for money; typed models give a precise OpenAPI file; one API serves both clients; Python leaves room for AI features | A TypeScript backend would share a language with both clients. Rejected: JavaScript has no decimal type, so money correctness would depend on discipline |
| 2 | Web: Next.js (App Router, TypeScript strict) | Server-side route handlers give the BFF layer; the largest body of examples | A plain SPA is simpler. Rejected: it would hold tokens in the browser |
| 3 | Mobile: Expo (React Native, TypeScript, Expo Router) | Camera, secure storage and a QR-code demo with no build | Flutter has better rendering control. Rejected: a second language and no reuse of generated types or tokens |
| 4 | Three folders: `backend/`, `frontend/`, `mobile/` | One folder per deliverable | A shared package would remove some duplication. Rejected: each client generates its own types from one OpenAPI file, so there is nothing to share |
| 5 | Everything runs through Docker Compose locally | Same environment on any machine, one command to start | Native tooling is faster to iterate. Accepted cost; polling handles file changes |
| 6 | Receipts in Cloudinary | One account, no storage servers, works the same locally and deployed | It is a third-party dependency in an otherwise self-contained stack. Mitigated by a storage interface and an in-memory fake for tests |
| 7 | Receipts are uploaded as authenticated (non-public) assets and fetched only through the API | Receipts are financial documents; a public URL cannot be revoked | Direct public URLs are simpler and cheaper. Rejected on privacy |
| 8 | Web uses a BFF: Next.js route handlers keep tokens in HttpOnly cookies | The browser never holds a readable token | More moving parts than storing a token in the browser. Kept: it is one catch-all route plus three auth routes |
| 9 | Ten large passes, not many small ones | Fewer restarts and less repeated context | A big pass hides problems for longer. Mitigated by isolating the ledger in its own pass and by review points inside passes |

## 2. Correctness

| # | Decision | Why | Strongest objection |
|---|---|---|---|
| 10 | Money is `NUMERIC(14,2)` and `Decimal`; percentages are integer basis points | A float cannot hold 0.10 | Integer minor units everywhere would be even safer. Rejected: noisier code for no gain with `Decimal` |
| 11 | Voucher balance is enforced by a **deferred constraint trigger** | Lines arrive one at a time; checking at commit keeps the database the authority even if a future endpoint is wrong | Service-only checks are simpler. Rejected: any code path could bypass them |
| 12 | Voucher numbers come from a counter row, assigned at Post | A sequence is not rolled back, so a failed transaction leaves a gap; numbering at Draft burns numbers on abandoned drafts | A sequence is faster. Irrelevant at this volume |
| 13 | Allocation uses the largest-remainder method in integer paisa, tie-break by id | Parts sum exactly to the total; the same cost centre gets the extra paisa each time | Giving the remainder to the largest share is simpler. Rejected: unfair and unstable on uneven splits |
| 14 | Void sets a status and creates a reversing voucher, posted at once, dated today, not itself voidable | History is never destroyed | Editing in place is simpler. Rejected: no audit trail |
| 15 | A draft voucher cannot be saved unbalanced; the editor holds unsaved lines in memory with a leave-page warning | The database refuses it, so there is one rule everywhere. A balance-check endpoint returns the difference and the fix | Long entries lose work on a crash. Mitigated by the warning; allowing unbalanced drafts would need a second set of rules |
| 16 | Two withholdings: sales tax by vendor registration, income tax (s.153) by vendor filer status | They are different taxes with different bases | One combined rule is simpler. Rejected: wrong for unregistered vendors |
| 17 | Tax rates live in a dated table, never in code; the resolved rate is copied onto the line | Rates change with each Finance Act | Hardcoding is quicker. Rejected: it would rewrite history |
| 18 | Idempotency keys: separate `post_key` and `void_key` columns | A key used to post must not block a void | One shared column is simpler. Rejected: couples two operations |
| 19 | Audit log is a plain append-only table, written in the same transaction | The brief asks for a log of every change | A tamper-evident chain is stronger. Rejected: not required, and it adds a global write lock |
| 20 | Email is sent after the transaction commits, as a FastAPI background task | Never email about a change that rolled back; the provider's latency or failure never blocks or fails the request (failures are logged) | An outbox table survives a process crash mid-send. Rejected: nothing here depends on guaranteed delivery, and the extension point is documented |
| 21 | Refresh-token reuse revokes all of that user's refresh tokens | Simple and safe at this scale | Token families are more precise. Rejected: more state for little gain |
| 22 | Rate limits are named policies held in memory, per process, with one API worker. No Redis | One API process and no other use for Redis; it would add a service, credentials, and a fail-open or fail-closed decision just for this | Counters reset on restart and are not shared between workers. If that matters, move the sensitive policies (login, reset, invite, Admin resends) to a Postgres counters table first, keep the per-request safety net in memory, and consider Redis only for very high-frequency limits |
| 23 | Password reset and invites share one `auth_tokens` table | Same shape: hashed, single use, expiring | Two tables are more explicit. Rejected: duplication |
| 24 | No approval limits or second-approver routing | Not in the brief | Real systems have them. Recorded as an extension point |

## 3. Product answers

| # | Question | Answer | Why | Strongest objection |
|---|---|---|---|---|
| 25 | Voucher year | Calendar year of the document date; a setting switches to fiscal (July to June) | The brief's example format reads as a calendar year; the switch covers the other case | Pakistani accountants think in fiscal years. Mitigated by the setting |
| 26 | Roles | The charter and matrix in section 4 | One clear purpose per role, with separation of duties enforced regardless of role | Too strict for a very small company. The matrix is the only place to change |
| 27 | Who is told when a vendor's bank account changes | The user who created the vendor and all admins | This is the standard invoice-redirection fraud vector | Noisy for large vendor lists. Rare event in practice |
| 28 | Tax category on a purchase line | `goods`, `services`, `contracts` or `any`; a specific rule beats `any` | Matches how section 153 groups payments | A finer taxonomy would be more accurate. Out of scope |
| 29 | Who edits tax rates | Admin only; effective dates may be in the past | A rate change affects every later purchase | Accountants may need to edit. They can ask an admin |
| 30 | Payment methods | `cash`, `bank_transfer`, `card`, `cheque` | Covers common office payments | Mobile wallets are common in Pakistan. Add as data later |
| 31 | Is an expense amount gross of tax | Yes; tax is recorded for reporting and never added on top | One unambiguous total | Some users enter net amounts. The label says gross |
| 32 | Can an expense change between direct and indirect | Only while it is a Draft; locked once submitted | Users pick the wrong type often, and a Draft has no numbering or posting to protect | Switching must clear attribution or allocations. Covered by a test |
| 33 | Does voiding a payment reopen its source | No | Posting is irreversible by rule | The obligation appears settled. Recorded as a known limitation |
| 34 | Posting accounts | A `posting_accounts` table seeded with defaults, editable by an admin | A fresh install must be able to generate a voucher | More configuration surface. Minimal endpoint only |
| 35 | Payment of purchases | A purchase links to the voucher that pays it; both directions navigable | Required by the brief | None |
| 36 | Receipts format | Images only (JPEG, PNG, WebP) | Phone capture is the main source | PDFs are common. Extension point |
| 37 | Mobile | Build the Expo app after the web QA, regardless of the client's reply | The brief lists mobile features explicitly | If the client accepts responsive web, the time could go elsewhere. The web app is already responsive |

## 3b. Scale, lists, caching and background work

| # | Decision | Why | Strongest objection |
|---|---|---|---|
| 38 | No server-side cache (no Redis) | Postgres serves small reference tables from memory already; stale data on money and status screens is a correctness risk, and invalidation is a new class of bug | Report aggregates could get heavy if the company grew a lot. The growth note in `architecture.md` section 14 lists checkpoints first, then a cache |
| 39 | Client-side caching only, through TanStack Query | Reference data (accounts, categories, cost centres, tax rules) is cached for minutes and refreshed on change; documents, balances and anything about money always refetch after a mutation and on focus | A stale picker could show a deactivated account. The API still rejects it, and the error is specific |
| 40 | No job queue (no Celery, no worker process) | The only slow side effects are email and exports. Email runs as a background task; exports stream | Large exports could time out. Documented extension point: a worker and a queue |
| 41 | Sized for a company of 20 to 30 people | The brief says "small company"; designing for more adds complexity with no benefit | A reviewer may expect scale reasoning. The short growth note covers it |
| 42 | Lists use `limit` and `offset` with a total count, page size clamped to 100 | At this size it is the simplest, and it gives users page numbers and a "showing 1 to 25 of 140" count, which accountants expect | Offset pages slow down and drift on very large, fast-changing tables. Irrelevant at a few thousand rows; a cursor would remove page numbers and totals |
| 43 | Direct expenses carry a project, product or cost centre. Projects and products share one table with a `kind` | The brief names all three. One table keeps the schema small | Separate tables are more explicit. Rejected: identical fields |
| 44 | A voucher generated from an expense or purchase is a Payment voucher, crediting cash for `cash` payments and bank for the rest | The brief says the voucher "pays" the purchase | Unpaid purchases would need a payable posting. A Journal voucher covers that by hand; recorded as an extension |
| 45 | Attachments (receipts) are allowed on expenses and purchases | The brief lists attachments on both | None |

## 3c. Access, public screens and onboarding

| # | Decision | Why | Strongest objection |
|---|---|---|---|
| 46 | One role per user | Keeps every permission check a single lookup. Admin already covers the Accountant and Approver abilities, so a person who wears two hats is made an Admin | A person who is both Approver and Accountant needs two roles. Rare in a company this size; multi-role can be added later without changing the checks |
| 47 | Only Admins invite users, change roles, deactivate users and trigger password resets | These are the actions that grant or remove access | Accountants may want to onboard staff. They ask an Admin |
| 48 | An Admin triggers a reset email; an Admin never sees or sets a password | A person who knows another user's password can act as them, which defeats the audit log | Setting a temporary password is quicker. Rejected on accountability |
| 49 | Invites expire after 7 days; reset links after 30 minutes; both are single use and stored hashed | Long enough to be practical, short enough to limit exposure | Longer invites are friendlier. An Admin can resend one |
| 50 | The last active Admin cannot be demoted or deactivated, and nobody can demote or deactivate themselves | Prevents locking everyone out | Looks restrictive. It has no cost in practice |
| 51 | Public screens are the login screen and its three siblings (forgot password, reset password, accept invite), all in one 50/50 split layout | Users are invited, so nobody arrives anonymously. One layout keeps them consistent; a split gives the brand a place without crowding the form | A split layout wastes space on small screens. Below the tablet breakpoint the panel collapses to a compact header |
| 52 | Approval emails stay (needs approval, decided); no notification preferences or digests | An approval workflow nobody is told about gets ignored; preferences add screens and storage for little value | Busy approvers may want a digest. Not in the brief |
| 53 | A short, role-aware, skippable onboarding tour, with completion saved on the server | The tour follows the user across devices; role-aware steps keep it short and relevant | Tours annoy people. It is skippable at every step and can be relaunched from the profile menu |
| 54 | A small tour library for the spotlight and positioning, not a hand-rolled one | Focus handling, scrolling and positioning are hidden complexity. Confirm current React 19 compatibility and keyboard behaviour first | Another dependency. Small, and it replaces a fiddly component |
| 55 | Mobile gets a three-card intro instead of a spotlight tour, using the same completion flag | A spotlight tour on a small screen is awkward | A consistent tour on both clients. The flag keeps them in step |
| 56 | Rate limits key on the email or user first and the IP second | The BFF hides browser addresses from the API and offices share one address, so IP-only limits are unreliable and unfair | IP limits are the usual default. They are kept as a second layer |
| 57 | Limits throttle; they never lock an account | A lockout lets an attacker deny a real user access | Throttling lets a patient attacker keep trying slowly. The window and the audit log make that visible |
| 58 | Time is UTC in storage, in the API, in logs and in exports; on screen it is one configured zone (`DISPLAY_TIMEZONE`, default `Asia/Karachi`), never the device's zone | Every device shows the same time for the same instant. Showing raw UTC to staff would put a 2 a.m. submission on the previous day; a fixed company zone matches how accountants think. Setting it to `UTC` shows UTC everywhere | Raw UTC on screen is the simplest and unambiguous. It is one setting away. The cost is that Pakistani users would do date arithmetic in their heads |
| 59 | Business dates (`document_date`, period and report ranges) are plain calendar dates and are never passed through a timezone | A date has no time; converting it is the classic cause of a document landing on the wrong day | A timestamp would carry more information. It would also carry the zone problem |
| 60 | The server stamps every business instant; a client never sends one | Devices have wrong clocks and wrong zones | Offline mobile captures need a time. They send their chosen `document_date` and a UTC instant for information only |
| 61 | Both clients format through one rule set (fixed zone, one format), with the zone served by the API | Consistency between web and mobile; no hydration mismatch when Next.js renders on the server in UTC | A library per platform is easier. Rejected: the formats would drift |
| 62 | Login failures are keyed on email and IP together (strict), email alone (loose) and IP alone, and counted before the password check | Stops a burst of parallel guesses, and stops an attacker slowing a user's own login by failing from a different address | More keys to maintain. Each closes a specific attack |
| 63 | The API trusts a client address only from the BFF, proven by a shared secret | The API is public, so any caller can send any forwarded-address header. Without a secret the IP limits can be spoofed, and the BFF's shared address can be exhausted to block every web login | A bare `X-Forwarded-For` is simpler. Rejected as spoofable |

## 3d. Build decisions

Made during the build under the protocol above.

| # | Decision | Why | Strongest objection |
|---|---|---|---|
| 64 | Synchronous SQLAlchemy 2 with psycopg 3 and sync FastAPI routes | At 20 to 30 users the threadpool is ample; sync code is simpler to test with real parallel connections and to reason about in transactions | Async scales further. Irrelevant at this size, and it would complicate the race tests |
| 65 | Primary keys are `BIGINT` identity columns, not UUIDs | Allocation tie-breaks by id ascending, which needs an ordered id; smaller indexes and readable ids in the audit log | Sequential ids can be guessed. Every read checks ownership and answers 404, so a guessed id reveals nothing |
| 66 | Services own the transaction and commit; the session dependency never commits | A commit failure (for example the deferred balance trigger) must surface inside the service as a domain error, before any response is sent; FastAPI's exit-code timing for yield dependencies has changed between versions | A dependency that commits is less code per service. Rejected: the failure would arrive after the handler returned |
| 67 | Runtime and dev packages implied by the named stack: uvicorn, psycopg, pydantic-settings, tzdata; dev: httpx2 (Starlette 1.7's test client asks for it, httpx is deprecated there) | Each is required by FastAPI, SQLAlchemy with PostgreSQL, the settings class, or `DISPLAY_TIMEZONE` | Not named in `architecture.md`. Approved by the owner |
| 68 | Two database roles: the owner runs migrations and creates scratch databases; `daftar_app` runs the API and has insert and select only on `audit_events`. Grants are re-applied at the end of every migration run | Makes "the audit log can only be appended to" true in the database, not just in the code | A trigger would also bind the owner, but it would block test clean-up. The role is the rule the architecture states |
| 69 | A reviewer may reject a document they created; only approving one's own is refused | Rejecting your own submission is a withdrawal and harms no one; the segregation rule is about approval | A strict reading blocks both. A withdraw action can be added without changing the table |
| 70 | `GET /me` returns only the display timezone in Pass 1 | The plan asks for it in Pass 1, before sign-in exists; Pass 2 adds the user and the tour flag | An unauthenticated `/me` is odd for a moment. It exposes one setting |
| 71 | `cacheComponents` and `partialPrefetching` from the Next.js template are off; the dev server polls files | Server-side caching is ruled out in decision 38 and the BFF pages depend on cookies; file events do not cross a Windows bind mount | Polling costs CPU. It is development only |
| 72 | Default host ports are 8001 (API) and 3001 (web) | Another project on the owner's machine holds 8000 and 3000. Owner's call | The plan says 8000 and 3000. Both are settings |
| 73 | Access tokens are HS256 JWTs (PyJWT) that carry only the user id and expiry; the role and active flag are read from the database on every request. Expiry is judged against the injected clock | A role change or deactivation applies at once, and tests can move time | Opaque tokens need a table lookup. The lookup happens anyway for the role, so signing buys little; JWT keeps the BFF and mobile clients simple and the token revocable only by deactivation, which is checked per request |
| 74 | Refresh tokens are opaque, stored as SHA-256 hashes, rotated on every use, and claimed with one atomic `UPDATE ... RETURNING`. Presenting a consumed or revoked token revokes all of that user's tokens | Decision 21, made safe under parallel use: of two simultaneous refreshes exactly one wins | A client that refreshes twice at once looks like theft and is signed out everywhere. The web app must refresh one request at a time (Pass 6) |
| 75 | A tax rule stores only the flag its tax depends on: sales tax withholding keys on registration (`supplier_filer` fixed false), income tax withholding on filer status (`supplier_registered` fixed false). A `CHECK` enforces it and lookups normalise the same way | The exclusion constraint compares every column, so an unused flag must hold a fixed value rather than null; it also makes the rule table smaller | `domain-rules.md` section 5 lists all four keys for every rule. The refinement removes duplicate rows without losing any distinction |
| 76 | Master-data rows carry a `version`, checked by SQLAlchemy's `version_id_col` and by a required `If-Match` header on every update | Two people editing the same vendor or rate cannot overwrite each other silently | An extra header on each update call. The clients already send it for documents |
| 77 | Password policy: 10 to 128 characters, not all one character, not the email address. No composition rules | Length protects better than symbols; matches current guidance | No check against known breached passwords. Out of scope without an extra service |
| 78 | Resending an invitation cancels the old one and creates a new one with a new id | A resend must kill the old link; one row per link keeps each hash single-use | The Admin's list shows both. The UI must use the id the resend returns |
| 79 | The console mailer writes the whole email, link included, to the log, in development only | There is no mail service until Pass 5, and a reset link must be reachable to test the flow | A token in a log breaks the logging rule. It is replaced by Mailpit and Resend in Pass 5; production never uses it |
| 80 | A database constraint violation is turned into its domain error by name in one handler (`CONSTRAINT_ERRORS`), not by a try/except in each service | The database stays the authority and the message stays specific | The map must be kept in step with the migrations; a test checks every name exists |
| 81 | Seeded withholding rates are illustrative starting values, every row marked UNVERIFIED with the sources that disagreed | Published figures differ and I could not reach the FBR schedule | They could be mistaken for law. The `source` field says otherwise, and an Admin edits them |
| 82 | One extra rate-limit policy, `reauth_user` (5 per 15 minutes), throttles password re-entry for a bank change or password change | A re-authentication prompt is a password-guessing oracle for someone holding a stolen session | A lockout would be safer against guessing but is ruled out by decision 57 |
| 83 | An uploaded image is accepted by its first bytes (JPEG, PNG, WebP), decoded and written out again with Pillow, which drops EXIF, GPS and every other tag. The SHA-256 is of the file as received. Limits: 10 MB, 40 million pixels, 10 attachments per document, 30 uploads per user per hour | The file name and the declared type are the client's word; re-encoding is the reliable way to remove metadata; hashing the original makes the same file recognisable | A re-encode changes the bytes, so the stored hash is not the stored file's hash. Duplicate detection needs the original's, so that is the one kept |
| 84 | Attachments are stored under a random key (`folder/kind/uuid`) as Cloudinary `authenticated` assets, and read back only through the API after the document's visibility check. A removed attachment keeps its row (`removed_at`) and loses its stored file. Development and tests use an in-memory store; production refuses it | No public URL to leak or revoke; the audit trail survives removal | The in-memory store loses receipts when the API restarts. That is acceptable for development |
| 85 | The rows under a document (allocations, purchase lines) are replaced when a draft is edited, so they can be deleted while Draft; database triggers freeze them, and the document's own fields, once it leaves Draft | An edit is simplest as "replace the set"; the freeze makes "read-only once submitted" a database rule | Allowing deletes weakens "nothing is deleted". Only draft working rows are removed; posted data never is |
| 86 | Only the author submits, edits or reopens a document, as a service rule; the transition table keeps the role rules and self-approval | The table says who may approve; "whose document" is a fact about the row, not the role | The check lives in each document service. A shared test over all three types keeps them in step |
| 87 | A document service locks the row (`SELECT ... FOR UPDATE`) before any change, and every move or edit needs the `If-Match` version | Two approvals at once cannot both succeed; the version check is a second layer that still holds if the lock is ever missing | The version can step by more than one per edit; clients treat it as an opaque token |
| 88 | Purchase withholding: sales tax is withheld on the sales tax shown (registered supplier) or on the gross value (unregistered); income tax on the gross including sales tax; each rounded once per line. A line category with no matching rule is refused (`TAX_RULE_MISSING`), never treated as zero | Domain rules section 5. A silent zero would under-withhold | Lines in the `any` category fail until an Admin adds an `any` income-tax rule. The screen offers goods, services and contracts |
| 89 | Editing a draft purchase prices it again and re-copies the rates | The vendor, the date or a line may have changed which rates apply; "copied when written" | A re-priced draft can differ from what the author last saw. The response shows the new figures |
| 90 | A percentage split stores the basis points and the exact amount; changing the expense amount recomputes it by largest remainder (ties to the lowest cost-centre id). A fixed split cannot be recomputed, so the caller sends the new amounts | The same cost centre gets the extra paisa every time; a fixed split has no rule to follow | A fixed split costs an extra step when the amount changes |
| 91 | Document reads carry `actions`: the moves this viewer may make now | The screens show only permitted actions without duplicating the role table | It is advice, not authority: the server still checks every move |
| 92 | A closed period answers 409 `PERIOD_CLOSED`, not 422 (`architecture.md` section 6 corrected to match `domain-rules.md` section 4) | The request is well formed; the state of the books forbids it, like a stale version | Two guards share one table row style in the docs; the error enum is the source of truth |
| 93 | The voucher year follows the document date. Calendar mode is the default; fiscal mode runs July to June and is named by the year it ends in (1 July 2026 is year 2027). A setting switches it | A number reads `PV-<year>-<seq>` and the year must not depend on the clock or the server's zone | The July start is an assumption for Pakistan; it is one setting and one function (`core/numbering.py`) |
| 94 | Numbers come from a counter row advanced by one statement, `INSERT ... ON CONFLICT DO UPDATE ... RETURNING last_seq`, inside the posting transaction | The row lock serialises posts for one type and year; a rollback undoes the increment, so there is no gap; the first post of a year needs no set-up | Posts for one type and year queue behind each other. Fine at this scale |
| 95 | A reversing voucher is born Posted, in the same transaction as the void, numbered from the same counter and dated today in the display zone. `core/transitions.start_posted` is the one place besides the table that assigns a status | The reversal must exist if and only if the original is void; walking it through Draft to Posted would need two roles and two commits | A second place assigns a status. A test fails if any other file does |
| 96 | Post and void need an `Idempotency-Key` (8 to 100 characters from a small set). The same key for the same voucher returns the first result; the same key for another voucher is 409 `IDEMPOTENCY_KEY_REUSED`; the key is stored on the voucher under a unique partial index | A double click or a retry after a timeout must not post twice; the database, not the service, decides which request won | Keys are kept for ever on the voucher (a few bytes each). A client that loses its key cannot replay, but posting again is refused as already posted |
| 97 | Only an Admin voids; approvers and bookkeepers cannot | Void is the one way to undo a posted voucher, so it takes the widest authority | An accountant who spots a mistake asks an Admin |
| 98 | Voucher lines can be deleted while the voucher is a Draft (so an edit replaces them); the freeze trigger refuses any change once it leaves Draft. Vouchers and counters are never deleted | Same reasoning as decision 85 | The no-delete trigger on `voucher_lines` that Pass 4 first had was removed |
| 99 | An account that has postings cannot be made a parent, raised as 409 `ACCOUNT_HAS_POSTINGS` by the same database check as the other tree rules | Closes the Pass 2 note: a posted-to account must stay postable | An Admin who wants a group above a used account adds a new parent and moves nothing |
| 100 | A purchase carries no expense category or payment method, so both are chosen when its voucher is generated (`category_id`, `payment_method`); an expense uses its own | Keeps the Pass 3 purchase API unchanged; the owner chose this | The same purchase could be paid by cash or bank depending on the day; the voucher records which |
| 101 | A starting chart (19 accounts, parents not postable), the five posting accounts and six expense categories are seeded by migration 0005, like the tax rules. The fast test database empties them after migrating so tests build their own; the fresh-install test keeps them | A fresh install must be able to generate a voucher with no set-up beyond a cost centre | The names and codes are a plain starting point and unverified; an accountant should review them, and an Admin can edit all of it |
| 102 | A generated expense voucher debits the net amount to the category's account (split over cost centres by the approved split) and the tax as its own line, never split; a purchase credits each withholding to its own liability line. An expense whose tax equals its whole amount cannot generate one (422) | Tax follows the posting account, not the cost centre; separate lines keep every liability visible | A voucher can have many lines |
| 103 | Email goes out through one of three transports chosen by `MAIL_BACKEND`: the console log (development), SMTP to Mailpit, or Resend's HTTP API. Both real ones use only the standard library; production refuses the console and Resend refuses to start without its key | No new dependency, and the same code path in every environment except the last hop | No retries and no queue, as decision 20 already accepts. A provider outage loses the email, and the log says which kind |
| 104 | A submit emails every active approver and admin except the author ("needs your approval"); an approve or reject emails the author ("decided", with the reviewer's comment). Nothing else. The messages are collected in the Outbox and sent by the router after the service returns, so a move that fails sends nothing | Decision 52 allows these two; admins can approve, so they are told | Admins who never approve get mail too. A notification preference is the fix and is out of scope (decision 52) |
| 105 | Expense and purchase reports count approved and posted documents unless the caller picks statuses; the voucher register shows posted and void. Staff see no reports | Approved spend is committed even before its voucher is posted; the register is the numbered books, with a void beside its reversal | A report that includes approved items is not the same as the ledger. The scope is echoed in every response and export so a printed copy says what it covers |
| 106 | Reports return their whole grouped result (bounded by cost centres and vendors); only the voucher register is paged. A CSV builds its rows in memory and streams them in chunks | The grouped reports are small by nature. Paging a sum would be wrong | A very large register export holds its rows in memory. The extension point is a worker (decision 40) |
| 107 | CSV: UTF-8 with a byte-order mark, amounts as plain two-place decimals, any text cell starting with `=`, `+`, `-`, `@`, tab or carriage return gets a leading apostrophe. Every export is limited to 10 per hour per user (checked before any query, after the filter is validated) and audited with its filter and row count in the same transaction | Domain rules section 9. A refused or invalid export leaves no audit row, because nothing was exported | The apostrophe shows in the cell. It is the usual price of safe spreadsheets |
| 108 | Duplicate warnings, advice only: a purchase warns for the same vendor and invoice number (ignoring case and spaces), the same vendor with a gross value within 1 per cent within 7 days, or an identical receipt (SHA-256); an expense warns for the same author and category with an amount within 1 per cent within 7 days, or an identical receipt. Rejected documents do not count. Staff are shown only their own documents. Served by a separate endpoint per document, not on every read | Domain rules section 8 says "similar" and "nearby" without numbers; these are the numbers. One banner per screen needs one extra request, a list needs none | 1 per cent and 7 days are judgement calls and live in `core/duplicates.py`. Two real purchases of the same amount in one week from one vendor will be flagged |
| 109 | `refresh_session` writes no audit row, nor do the three previews, the balance check or the invitation inspection. Every other mutating route does, in the same transaction as its change. A test lists every route and proves both facts by making the audit insert fail and checking that nothing else changed | A refresh happens every few minutes per user and only rotates a token; the dangerous case, a spent token used again, is audited. The others save nothing | The list of exceptions is short and each has its reason in the test, so a new route cannot slip in unaudited |
| 110 | The seed uses the real services, in date order, with its own clock, as the four demonstration people. Dates are relative to the day it runs: finished work falls in the two months before this one and is then closed, work in progress falls in this month. It never runs in production, runs twice harmlessly, and publishes its password (`daftar-demo-2026`) on purpose | A seed that bypassed the services could produce data the app would refuse. Relative dates keep the demonstration current whenever it is run | With the in-memory receipt store (the development default) the seeded receipts disappear when the API restarts. Cloudinary keeps them. Open question for the owner |
| 111 | `backend/openapi.json` is generated by `python -m app.openapi_export`, committed, and a test fails when it is stale. The API list in `docs/api.md` is generated from it. CI runs the same Docker Compose gates as a developer machine | The contract cannot be written by hand, and CI cannot disagree with a local run | `docs/api.md` is not covered by the stale test (the container cannot see `docs/`); it is regenerated by `make openapi` |
| 112 | Whether the onboarding tour is done is stored on the server, per person: `POST /me/tour/complete` stamps the time (a second call changes nothing) and `POST /me/tour/restart` clears it. Both are audited | The tour must follow a person across web and mobile, and skipping it counts as done | A person who completes the tour on a phone will not be shown it on the web. That is the intent |

## 4. Roles

One role per user. Roles are read from the database on every request, so a change applies at once.

| Role | Purpose | Can | Cannot |
|---|---|---|---|
| Admin | Runs the system and the company setup | Invite users, assign roles, deactivate users, trigger password resets, resend or revoke invites; manage tax rates, periods and posting accounts; everything an Accountant and an Approver can do; void; read the audit log | Approve or post a document they created; change their own role or deactivate themselves; remove the last active Admin; see or set anyone's password |
| Accountant | Keeps the books | Maintain master data; create and submit purchases and vouchers; generate vouchers from approved items; post; reports and CSV | Approve or reject; void; manage users, tax rates or periods |
| Approver | Reviews and decides | Read all documents and reports; approve or reject expenses, purchases and vouchers, with a comment | Create or edit documents; post or void; change master data |
| Staff | Records their own spending | Create, edit and submit their own expenses with receipts; see their own status and history | See anyone else's expenses; see vendors, accounts or reports |

| Action | Admin | Accountant | Approver | Staff |
|---|---|---|---|---|
| Invite users, change roles, deactivate users, trigger resets, resend or revoke invites | yes | no | no | no |
| Manage tax rates, close periods, edit posting accounts | yes | no | no | no |
| Create and edit vendors, accounts, categories, cost centres, projects and products | yes | yes | no | no |
| Read vendors and accounts | yes | yes | yes | no |
| Read cost centres, projects, products, categories | yes | yes | yes | yes |
| Create, edit and submit expenses | yes | yes | no | yes (own only) |
| Read expenses | all | all | all | own only |
| Create and submit purchases and vouchers | yes | yes | no | no |
| Approve or reject (never your own) | yes | no | yes | no |
| Post | yes | yes | no | no |
| Void | yes | no | no | no |
| Read reports and export CSV | yes | yes | yes | no |
| Read the audit log | yes | no | no | no |
| Take the onboarding tour, change own password | yes | yes | yes | yes |

**Rules that hold for every role**
- Nobody approves a document they created, for all three document types.
- Only the creator edits a Draft or reopens a rejected document.
- Voiding is Admin-only because it is the most destructive action.
- Every role change, invite, reset, deactivation and void is audited.

## 5. Not built, with the extension point

| Item | Where it would plug in |
|---|---|
| OCR on receipts | The upload handler, after the signature check |
| Virus scanning | The same place |
| Multi-currency | The `currency` column already exists on money tables |
| Approval limits | A rules table read by the transition guard |
| Tamper-evident audit | A hash column written by the audit service |
| Shared rate-limit store, read replica, partitioning | `architecture.md` section 14 |

If time runs out, cut in this order: trial balance report, audit screen, density toggle, onboarding tour, approval notification
emails (invite and reset emails stay), dark-mode polish, mobile beyond capture and approve. Never cut: the balance rule and its tests, the status tests, numbering, void and
reversal, one working end-to-end flow, the audit log, the progress logs.

## 5b. Deliberately not done, with reasons

| Not done | Reason |
|---|---|
| Landing or marketing page | Every user is invited by an Admin, so nobody arrives from the internet. A public page would only advertise an internal finance system |
| SEO (metadata for search, Open Graph and Twitter cards, sitemap, structured data) | Search visibility is a liability for an internal tool. The aim is the opposite, so `robots.txt` disallows everything and every route sends `noindex` |
| Terms of Service and Privacy Policy pages | These exist for public services that collect data from the public. Here the users are the company's own staff, who are covered by their employer's own policies. A template page would be filler and could be mistaken for legal advice. If the company needs a privacy notice, it must come from them. The README and security notes list what is stored: names, work emails, receipts, vendor bank details |
| Accessibility statement and `security.txt` | Conventions for public websites. There is no public site. Accessibility itself is built and tested in the app |
| Notification preferences and digests | Not in the brief. Two emails (needs approval, decided) are enough, and preferences add settings screens and storage |
| Self-signup | The company controls who has access. Accounts exist only by invitation |
