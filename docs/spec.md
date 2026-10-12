# Spec

What was asked for, and how the design handles each part. Read this with `architecture.md` and `domain-rules.md`.

## 1. Brief coverage, line by line

Build an Expense, Purchase and Voucher manager for a small company: web and mobile, one shared backend, in two
working days. Claude Code is used for the build and the process is shown.

| Brief says | Covered by |
|---|---|
| Working web app and a mobile app, one shared backend | Passes 1 to 8 (backend, web), Pass 9 (Expo) |
| Use Claude Code and show the process | `workflow.md`, `PROMPTS.md`, transcripts, `docs/MISTAKES.md` |
| Timebox: two working days; a smaller finished scope beats a bigger broken one | Cut order in `decisions.md` section 5; the never-cut list |
| **2.1** Direct expenses carry a project, product or cost centre | `projects` holds projects and products (a `kind` column); `CHECK` on the expense (decision 43) |
| Indirect expenses: no project, allocated across cost centres by percentage or fixed amount | Largest-remainder allocation, deferred sum triggers, preview endpoint |
| Fields: date, category, amount, tax, payment method, description, receipt, status | `domain-rules.md` section 6; Cloudinary receipts |
| Flow Draft, Submitted, Approved or Rejected, Posted | One transition table (`core/transitions.py`) |
| **2.2** Registered vendors: tax invoice number, sales tax amount, standard withholding | Vendor flags, `tax_rules` table, both withholdings, invoice number `CHECK` |
| Non-registered vendors: purchase or cash memo, different treatment, visible flag | Document kind `purchase_memo`, flag on screen, in print and in CSV |
| Purchase lines (item, quantity, rate, tax), vendor, date, attachments, status | `purchase_lines`, attachments on purchases and expenses, shared workflow |
| Link to the voucher that pays it | Generated Payment voucher, linked both ways (decision 44) |
| Vendor master: name, registered, NTN, STRN, contact, bank details | Vendors table; bank details encrypted and masked |
| **2.3** Types Payment, Receipt, Journal | `PV`, `RV`, `JV` |
| Lines debit or credit against accounts; total debit equals total credit | Chart of accounts; deferred constraint trigger |
| Auto-number per type and year (`PV-2026-0001`) | Counter row, assigned at Post |
| Flow Draft, Submitted, Approved, Posted, Void; void keeps an audit trail, never deletes | Void creates a reversing voucher; nothing is deleted |
| Generate a voucher from an approved expense or purchase | Voucher factory with the category-to-account mapping |
| **2.4** Roles Admin, Accountant, Approver, Staff | Role charter and matrix in `decisions.md` section 4; ownership checks in services |
| Approval workflow with comments and history | `document_events`, one timeline for all three document types |
| Audit log of every create, update and status change | Append-only `audit_events`; a test proves every mutating route writes one |
| Reports: expenses by type and cost centre, purchases by vendor (registered or not), voucher register, CSV | Pass 5 reports; allocated amounts count toward cost centres |
| Web: full feature set. Mobile: capture with receipt photo, view and approve, view vouchers | Passes 6 and 7; Pass 9 |
| **3** The candidate chooses the stack and why | `decisions.md` section 1 (choice, why, strongest objection) |
| Money as integers or decimals, never floats | `NUMERIC(14,2)`, `Decimal`, integer basis points |
| Automated tests for the voucher balancing rule and the status transitions | Passes 1 and 4; run in CI |
| **4.1** Git repository with a clean commit history | One commit per coherent step, messages as `add:`, `updated:` or `fixed:` with the story ID in brackets |
| **4.2** `CLAUDE.md` used in the project | Repo root |
| **4.3** `PROMPTS.md`: every significant prompt, in order, with model and effort and a reason | Repo root; `workflow.md` section 9 |
| **4.4** Exported session transcripts and approximate token cost | `docs/transcripts/`; `/cost` per pass |
| **4.5** `docs/`: spec, ERD, process flow, UI flow, API list | `spec.md`, `erd.md`, `process-flow.md`, `ui-flow.md`, `api.md` (Pass 10) |
| **4.6** Live URL or local run steps, and a five-minute recording | Pass 8 deploy; Pass 10 recording; README quickstart |
| **4.7** A short note on what the AI got wrong and how it was caught | `docs/MISTAKES.md` |

## 2. Requirement to design (see `architecture.md` for the diagrams)

### Expenses
| Requirement | How it is handled |
|---|---|
| Direct expense carries a project, product or cost centre | `CHECK` constraint on the table, and the service validates first |
| Indirect expense is allocated by percentage or fixed amount | `expense_allocations` rows. Largest-remainder in `core/allocation.py` splits in integer paisa so the parts always sum to the total. A deferred trigger re-checks the sum at commit |
| Fields: date, category, amount, tax, payment method, description, receipt, status | Plain columns. `document_date` (DATE, accounting) is separate from `created_at` |
| Status Draft, Submitted, Approved or Rejected, Posted | One transition table in `core/transitions.py` shared by all three document types |
| Receipt attachment | Stored in Cloudinary as authenticated assets through one storage interface. Served only through an authenticated API endpoint. Type checked by file signature, size capped, EXIF removed, SHA-256 stored |

### Purchases
| Requirement | How it is handled |
|---|---|
| Registered vendor: tax invoice number, sales tax, withholding | Vendor flag decides the document kind. Invoice number is required by a `CHECK`. Rates come from a dated `tax_rules` table, never from code; the resolved rate is copied onto each line |
| Non-registered vendor: memo, different withholding, visible flag | Document kind `purchase_memo`, a flag shown on screen, in print and in CSV. Withholding is on gross value because no sales tax was charged |
| Line items, vendor, date, attachments, status, link to the paying voucher | `purchase_lines` table. Totals are recomputed on the server, never trusted from the client. The voucher link is a column set at voucher generation |
| Vendor master with NTN, STRN, contact, bank details | `vendors` table. A `CHECK` requires NTN and STRN when registered. A second flag records filer (ATL) status because income tax withholding depends on it, not on registration. Bank details are masked in every response |

### Vouchers
| Requirement | How it is handled |
|---|---|
| Types Payment, Receipt, Journal | Type column; one voucher table, one lines table |
| Total debit equals total credit | A **deferred constraint trigger** checks at commit. A `CHECK` ensures each line has exactly one side. The API also offers a balance-check endpoint that returns the difference and the offsetting line so the UI can fix it in one click |
| Auto-number per type and year (`PV-2026-0001`) | A counter row per (type, year), incremented with `UPDATE ... RETURNING` inside the posting transaction. Assigned only at Post, so abandoned drafts leave no gaps. A PostgreSQL sequence is not used because it is not rolled back |
| Status Draft, Submitted, Approved, Posted, Void | Same transition table |
| Void keeps an audit trail, never deletes | Void sets the status and creates a reversing voucher in the same transaction. A partial unique index allows only one reversal per original |
| Generate from an approved expense or purchase | A factory builds default lines from a category-to-account mapping. Tax lines stay separate. Generating twice from one source is blocked |
| Retried requests must not double-post | `Idempotency-Key` header, with unique indexes on the post key and the void key |

### Cross-cutting
| Requirement | How it is handled |
|---|---|
| Roles Admin, Accountant, Approver, Staff | A role dependency on every route, plus an ownership check in the service. Another user's record returns 404, not 403 |
| Approval workflow with comments and history | `document_events` table: actor, action, comment, time. One table and one timeline component for all three document types. Nobody approves their own document |
| Audit log of every create, update and status change | Append-only `audit_events` table. The app's database role has insert and select only. Written in the same transaction as the change |
| Reports and CSV export | Reads from the same tables. Expenses by type and cost centre, purchases by vendor (registered or not), voucher register. CSV neutralises cells starting with `=`, `+`, `-`, `@` and is written as UTF-8 with a byte-order mark so Excel reads it |
| Web full, mobile capture and approve and view | Same API. The Expo app uses the same OpenAPI contract, tokens and error codes |
| Money never float | `NUMERIC(14,2)`, `Decimal`, integer basis points. Floats rejected at the boundary |
| Tests for balancing and transitions | Required, and they are the files a reviewer reads first. Balance: database-level and service-level. Transitions: every pair, listed and unlisted |

### Quality
| Concern | How it is handled |
|---|---|
| Security | argon2id. Short-lived access token, rotating refresh token stored hashed. Rate limits on login, reset, invites, uploads, exports and the API. Browser never sees a token (BFF cookies). CORS allowlist. Security headers. Upload validation. Log redaction |
| Errors | One error-code enum. One handler returns RFC 7807 JSON with a code and a correlation id. The UI maps each code to its own wording, with a fallback for unknown codes. Custom 404, 403, 500 and offline pages |
| Concurrency | Row lock on the counter, unique idempotency indexes, a `version` column on documents, deferred triggers. Isolation stays at `READ COMMITTED` because every rule is held by a lock or constraint |
| Scale | Sized for a company of 20 to 30 people. One small PostgreSQL and one API process. Paginated lists, indexed filter and sort columns, no N+1. Growth options are listed in `architecture.md` section 14 |
| Responsive and dark/light | Semantic CSS variables, three theme states (System, Light, Dark), tested at 360, 768, 1024 and 1440 px |
| Public surface | The login screen and its three siblings only, in a 50/50 split. No landing, SEO or legal pages; reasons in `decisions.md` section 5b. Every route is `noindex` and `robots.txt` disallows everything |
