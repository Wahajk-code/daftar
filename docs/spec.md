# Spec

What the brief asked for, and where each part is in the product. Read with `architecture.md` and `domain-rules.md`.

**The brief:** an Expense, Purchase and Voucher manager for a small company, with a shared backend, built with Claude Code, with the
process shown. **What was built:** a FastAPI API, a PostgreSQL database and a Next.js web app that is responsive and installs as a
phone app (PWA) with camera capture for receipts. There is no native mobile app (decision 148).

## Requirements and where they are

| Brief | Where |
|---|---|
| **Expenses.** Direct (project, product or cost centre) or indirect (split across cost centres by percentage or fixed amount); date, category, amount, tax, payment method, description, receipt, status | `ExpenseForm`, `core/allocation.py` (largest remainder, sums exactly), `CHECK` on the table, deferred sum triggers, allocation preview endpoint |
| Flow Draft, Submitted, Approved or Rejected, Posted | One transition table, `core/transitions.py` |
| **Purchases.** Registered vendors: tax invoice number, sales tax, withholding. Non-registered: purchase or cash memo, different withholding, visible flag | Vendor flags, dated `tax_rules` table, document kind `purchase_memo`, flag on screen, print and CSV |
| Lines (item, quantity, rate, tax), vendor, date, attachments, status, link to the paying voucher | `purchase_lines` (server-priced), attachments, generated voucher linked both ways |
| Vendor master: name, registered, NTN, STRN, contact, bank details | `vendors`; bank details encrypted and masked |
| **Vouchers.** Payment, Receipt, Journal; debit equals credit | `PV`, `RV`, `JV`; chart of accounts; deferred constraint trigger |
| Auto-number per type and year (`PV-2026-0001`) | Counter row, assigned at Post, gapless |
| Flow Draft, Submitted, Approved, Posted, Void; void keeps the trail | Void posts a reversing voucher; nothing is deleted |
| Generate a voucher from an approved expense or purchase | Voucher factory with category-to-account mapping |
| **Roles** Admin, Accountant, Approver, Staff | Role charter in `decisions.md` section 4; role guard on every route plus ownership checks |
| Approval workflow with comments and history | `document_events`; one timeline for all three document types |
| Audit log of every create, update and status change | Append-only `audit_events`; a test proves every mutating route writes one |
| **Reports** expenses by type and cost centre, purchases by vendor (registered or not), voucher register, CSV | Reports screen; list exports for expenses and purchases; injection-safe CSV |
| **Web** full feature set; **phone** capture with receipt photo, view and approve, view vouchers | Responsive web app; installable PWA with a camera button (`ui-flow.md`) |
| **Stack** chosen and justified | `decisions.md` section 1 |
| Money never a float; tests for voucher balancing and status transitions | `NUMERIC(14,2)`, `Decimal`, basis points; `tests/db/test_ledger_rules.py`, `tests/unit/test_transitions.py` |

## Deliverables

| Deliverable | Where |
|---|---|
| Git repository with a clean history | One commit per coherent step (`add:`, `updated:`, `fixed:`) |
| `CLAUDE.md` | Repo root |
| `PROMPTS.md`: every significant prompt, with model and effort | Repo root |
| Session transcripts and approximate token usage | `docs/transcripts/` (index and usage in its README) |
| `docs/`: spec, ERD, process flow, UI flow, API list | `spec.md`, `erd.md`, `process-flow.md`, `ui-flow.md`, `api.md` |
| Live URL and local run steps | `README.md`, `deploy.md` |
| A note on what the AI got wrong | `docs/MISTAKES.md` |

## Quality

| Concern | How |
|---|---|
| Security | See `security.md` |
| Errors | One error-code enum, one handler, RFC 7807 JSON with a correlation id; every code has its own wording on screen |
| Concurrency | Row lock on the counter, unique idempotency indexes, `version` on documents; real parallel tests |
| Scale | 20 to 30 people; paginated lists, indexed filters, no N+1 (a query-count test) |
| Look | Soft monochrome design with three-tier tokens, light by default and a dark theme, checked at phone and desktop widths |
| Public surface | Sign-in, forgot password, reset password and accept invite only; every route is `noindex` |
