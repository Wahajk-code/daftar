# User stories

The story ID is the single key linking this file, the test name, the commit message and the
`PROMPTS.md` entry. One identifier, four places, nothing restated.

Format: *As a `<role>`, I want `<action>`, so that `<outcome>`.* AC = acceptance criteria.

---

## Epic A — Access and identity

**A1** — Sign in with email and password.
AC: argon2id hashing; a generic error revealing nothing about whether the email exists; identical
response timing either way; five failures per minute per IP and five per 15 minutes per email;
returns a 15-minute access token and a rotating refresh token.

**A2** — Admin invites users, assigns one role each, and manages them.
AC: one role per user; roles are `admin`, `accountant`, `approver`, `staff`; role changes are audited and apply on the
next request; a user cannot change their own role or deactivate themselves; the last active Admin cannot be demoted or
deactivated; users deactivate, never delete; only Admins invite, change roles, deactivate or trigger resets.

**A3** — The UI shows only permitted actions and the API refuses the rest.
AC: every endpoint declares its required role; Staff calling an approval endpoint gets 403; Staff
requesting another user's expense gets 404, not 403, so existence is not leaked.

**A4** — Nobody approves their own document.
AC: submitter id cannot equal approver id; enforced in the service; tested for all three document
types.

---

## Epic B — Master data

**B1** — Vendors with name, registration status, NTN, STRN, contact and bank details.
AC: NTN and STRN required when `is_sales_tax_registered`; bank account masked in list views and
never written to logs; vendors deactivate once referenced; changing bank details requires
re-authentication, emails the owner and logs before/after.

**B2** — A separate ATL (filer) flag.
AC: independent of sales tax registration; the two drive different withholding rates.

**B3** — Chart of accounts with type (`asset`/`liability`/`income`/`expense`/`equity`) and hierarchy.
AC: parent accounts are not postable; an account with postings cannot be deleted.

**B4** — Cost centres and projects.
AC: deactivatable; inactive ones vanish from new-document pickers but still render on historical
documents, greyed with a tooltip.

**B5** — Withholding rates with an effective-from date.
AC: resolved by (tax type, registration, ATL status, category, document date); the resolved
`rate_bp` and `tax_rule_id` are snapshotted onto the line; editing the rate table never changes an
existing document; overlapping rules are rejected by an exclusion constraint.

---

## Epic C — Expenses

**C1** — Record a direct expense against a project, product or cost centre.
AC: attribution mandatory for `direct`; fields are date, category, amount, tax, payment method,
description, receipt, status.

**C2** — Record an indirect expense allocated across cost centres by percentage or fixed amount.
AC: percentages in basis points totalling exactly 10,000; fixed amounts totalling exactly the
expense; live remainder shown in the UI; largest-remainder allocation so the parts sum exactly;
deterministic tie-break so the same centre receives the leftover paisa on every recalculation.

**C3** — Attach a receipt.
AC: type validated by magic bytes not extension; size capped; stored privately under a random key;
served by short-lived signed URL; EXIF and GPS stripped; SHA-256 recorded.

**C4** — Submit for approval.
AC: validates completeness and allocation totals; becomes read-only to the submitter.

**C5** — Approve or reject with a comment.
AC: comment mandatory on reject, optional on approve; both recorded with actor and timestamp.

**C6** — Post an approved expense.
AC: generates a voucher; irreversible; no further edits.

**C7** — A rejected expense returns to Draft.
AC: original submitter only; the rejection comment stays visible in history.

---

## Epic D — Purchases

**D1** — Line items with item, quantity, rate and tax.
AC: line total and header total recomputed server-side in Decimal; never trusted from the client.

**D2** — Registered vendor.
AC: tax invoice number required; sales tax captured; both withholdings resolved from the rate
table; withheld amount and amount payable to vendor both displayed.

**D3** — Unregistered vendor.
AC: recorded as `purchase_memo` rather than `tax_invoice`; the flag renders on screen, in print and
in CSV; withholding computed on gross value, because no sales tax was charged.

**D4** — Same approval lifecycle as expenses.
AC: same transition table, same history component, no separate code path.

**D5** — Link between a purchase and the voucher that paid it.
AC: bidirectional and navigable.

**D6** — Attach documents to a purchase. AC: same checks and storage as expense receipts (signature, size, EXIF, SHA-256, authenticated).

---

## Epic E — Vouchers

**E1** — Payment, Receipt or Journal voucher with debit and credit lines.
AC: each line has an account and exactly one side; amounts positive.

**E2** — Refuses to submit unless balanced.
AC: running difference displayed while editing; Submit disabled while non-zero; a one-click action
inserts the exact offsetting line; the database rejects an unbalanced voucher at commit regardless
of what the API does.

**E3** — Numbered continuously per type and year.
AC: `PV-2026-0001`; assigned at Post; unique on (type, year, seq); N simultaneous posts yield N
distinct consecutive numbers.

**E4** — Generated from an approved expense or purchase.
AC: default lines from the category→account mapping; tax lines separate, not netted; opens in Draft;
generating twice from the same source is blocked.

**E5** — Post an approved voucher.
AC: idempotent under an idempotency key; posted lines can never be updated or deleted.

**E6** — Void with a mandatory reason.
AC: generates a linked reversing voucher with sides swapped; at most one reversal per original,
enforced by the database; the original is never modified beyond its status.

---

## Epic F — Workflow, audit and trust

**F1** — One shared transition table drives all three document types.
AC: roles named per transition; invalid transitions return 409 with a machine-readable code; tests
cover every valid transition and every invalid pair.

**F2** — Approval history timeline.
AC: chronological actor, action, comment, timestamp; one component across all three types.

**F3** — Every create, update and status change logged.
AC: written in the same transaction; actor, entity, before, after, correlation id; the application
database role has INSERT and SELECT only on the audit table.

---

## Epic G — Reports

**G1** — Expenses by type and cost centre. AC: filterable; Decimal totals matching the ledger.
**G2** — Purchases by vendor split registered vs unregistered. AC: withheld amounts shown separately.
**G3** — Voucher register. AC: chronological per type and year; voids marked and linked to reversals.
**G4** — CSV export. AC: values starting `= + - @` neutralised; plain decimals with no thousands
separators; UTF-8 with BOM so Excel reads Urdu correctly; every export logged with filter and row count.

---

## Epic H — Phone (the installed web app)

**H1** — A camera button on a phone starts an expense from a photo of a receipt. AC: the photo is turned upright and shrunk
before upload; the form opens with today's date.
**H2** — *Not built.* Captures that survive a bad connection need offline support (a service worker and a queue); the app has
neither (decision 148).
**H3** — View and approve or reject items awaiting approval, from the phone, with a comment. AC: same server rules as on a computer.
**H4** — Vouchers can be read on a phone.
**H5** — Tokens are never readable by the page (HttpOnly cookies) and are cleared on sign-out.

---

## Epic I — Email

**I1** — Password reset by email (self-service). AC: random single-use token, 30-minute expiry, stored hashed;
identical response whether or not the email exists; using the link signs the user out everywhere.
**I2** — Approver notified on submission. AC: type, number, amount, submitter, deep link that
survives the login redirect.
**I3** — Submitter notified on approval or rejection. AC: rejection comment included.
**I4** — Admin invites a user by email with a role. AC: 7-day expiry; single use; the invitee sets their own name and
password; an email that already has an account is refused; audited.
**I5** — Email is sent only after the change commits. AC: a rolled-back change sends no email. Tested.
**I7** — Admin triggers a password reset for a user. AC: sends the user the same reset email; the Admin never sees or
sets the password; audited.
**I8** — Admin resends or revokes a pending invite. AC: a revoked or expired link shows a clear message; audited.

---

## Epic J — Operational basics

**J1** `/health`, `/ready`, `/version` with git SHA · **J2** structured JSON logs with a correlation
id reaching the audit row, no PII · **J3** error tracking tagged by release · **J4** forward-only
migrations, no destructive change in the same release as the code that stops using the column ·
**J5** backups and a tested restore with the timing recorded · **J6** rate limits and body caps at
proxy and application · **J7** pooled connections · **J8** graceful shutdown · **J9** CORS allowlist,
security headers, HSTS, HTTPS redirect, secrets from env · **J10** `make seed` and `make reset`.

---

## Epic K — Reviewer experience

**K1** — Four pre-seeded accounts, a credentials panel on the login page, one-click role switching.
**K2** — Realistic Pakistani seed data; no lorem ipsum, no `Acme Corp`.
**K3** — A 60-second README quickstart: live URL, credentials, three-command local run, test command.
**K4** — Print stylesheet for vouchers and purchases; clean A4 with number, parties, lines, totals,
signature blocks.
**K5** — Empty, loading and error states on every screen; real 404 and 500 pages.

---

## Epic L — Domain correctness traps

**L1** fiscal vs calendar year in the voucher number — decided, configurable, documented ·
**L2** `document_date DATE` distinct from `created_at` · **L3** UTC stored and sent; one configured display zone, never the device's zone ·
**L4** period locking · **L5** one number formatter across screens and CSV · **L6** no N+1, with
a query-count assertion on list endpoints · **L7** disable on submit plus an idempotency key ·
**L8** never optimistic UI for money actions · **L9** session expiry preserves the draft and the
intended URL · **L10** *not built* (offline banner and queue; no offline mode) ·
**L11** virus scanning is a stated non-goal with a named extension point.

---

## Epic M — Public surface

**M1** — The only public screens are login, forgot password, reset password and accept invite. AC: all four share one
50/50 split layout (brand panel and form); below the tablet breakpoint the panel collapses to a compact header above the
form; every other route needs a session; `robots.txt` disallows everything and every route sends `noindex`; a demo-accounts
helper appears under the form only when `DEMO_MODE` is on.
**M2** — The footer shows the app version and git SHA.

## Epic N — Onboarding

**N1** — A short guided tour on first sign-in. AC: 4 to 6 steps chosen for the user's role; Skip is always visible and
Escape closes it at any step; finishing or skipping is saved on the server so it does not return on another device; "Take the
tour" in the profile menu relaunches it; keyboard accessible with focus managed; correct at 360 px and in both themes;
never blocks the app. It is written for the person (name, role, what is waiting), starts on first sign-in and can be started again only from the Help center.
