# Story matrix

Tick each box only when you have seen the evidence yourself. B = backend test, F = screen or frontend check, M = mobile.

Name every test so it contains its story ID, for example `test_e3_posts_get_consecutive_numbers`.
Find the tests for a story with: `Select-String -Path backend\tests\*.py -Pattern 'test_e3_'`

| ID | Story | B | F | M |
|---|---|---|---|---|
| A1 | Sign in with email and password | [x] | [ ] | [ ] |
| A2 | Admin invites users, assigns one role each, manages them | [x] | [ ] | n/a |
| A3 | UI shows permitted actions; API refuses the rest; other user's record is 404 | [x] | [ ] | n/a |
| A4 | Nobody approves their own document (all three types) | [x] | [ ] | n/a |
| B1 | Vendors with NTN, STRN, contact, bank details (masked) | [x] | [ ] | n/a |
| B2 | Separate ATL (filer) flag on vendors | [x] | [ ] | n/a |
| B3 | Chart of accounts with hierarchy; parents not postable | [x] | [ ] | n/a |
| B4 | Cost centres and projects, deactivatable | [x] | [ ] | n/a |
| B5 | Tax rules by date; rate copied onto the line | [x] | [ ] | n/a |
| C1 | Direct expense against project, product or cost centre | [ ] | [ ] | [ ] |
| C2 | Indirect expense allocated by percentage or fixed, exact sums | [ ] | [ ] | n/a |
| C3 | Receipt attachment, validated, private, stripped | [ ] | [ ] | [ ] |
| C4 | Submit an expense for approval | [ ] | [ ] | [ ] |
| C5 | Approve or reject with a comment | [ ] | [ ] | [ ] |
| C6 | Post an approved expense (creates a posted voucher) | [ ] | [ ] | n/a |
| C7 | Rejected expense returns to Draft for its author | [ ] | [ ] | n/a |
| D1 | Purchase lines; totals recomputed on the server | [ ] | [ ] | n/a |
| D2 | Registered vendor: invoice number, sales tax, both withholdings | [ ] | [ ] | n/a |
| D3 | Unregistered vendor: purchase memo, visible flag, gross-value withholding | [ ] | [ ] | n/a |
| D4 | Purchases use the same lifecycle as expenses | [ ] | [ ] | n/a |
| D5 | Purchase and its paying voucher link both ways | [ ] | [ ] | n/a |
| D6 | Attach documents to a purchase | [ ] | [ ] | n/a |
| E1 | Voucher with debit and credit lines, one side per line | [ ] | [ ] | n/a |
| E2 | Cannot save unbalanced; running difference; one-click balancing line | [ ] | [ ] | n/a |
| E3 | Gapless numbering per type and year, assigned at Post | [ ] | [ ] | [ ] |
| E4 | Generate a voucher from an approved expense or purchase | [ ] | [ ] | n/a |
| E5 | Post is idempotent; posted lines are immutable | [ ] | [ ] | n/a |
| E6 | Void with reason creates one linked reversal | [ ] | [ ] | n/a |
| F1 | One transition table; every valid and invalid pair tested | [x] | n/a | n/a |
| F2 | Approval history timeline, one component for all types | [ ] | [ ] | [ ] |
| F3 | Audit row for every create, update, status change | [ ] | n/a | n/a |
| G1 | Expenses by type and cost centre | [ ] | [ ] | n/a |
| G2 | Purchases by vendor, registered versus not | [ ] | [ ] | n/a |
| G3 | Voucher register, voids linked to reversals | [ ] | [ ] | [ ] |
| G4 | CSV export, injection-safe, UTF-8 with BOM | [ ] | [ ] | n/a |
| H1 | Camera-first capture, compressed, prefilled | n/a | n/a | [ ] |
| H2 | Capture survives a bad connection; no duplicates | n/a | n/a | [ ] |
| H3 | View and approve or reject items from the phone | n/a | n/a | [ ] |
| H4 | Vouchers viewable read-only | n/a | n/a | [ ] |
| H5 | Tokens in secure storage, cleared on logout | n/a | n/a | [ ] |
| I1 | Password reset by email (self-service) | [x] | [ ] | n/a |
| I2 | Approver emailed on submission | [ ] | n/a | n/a |
| I3 | Submitter emailed on approve or reject | [ ] | n/a | n/a |
| I4 | Admin invites a user by email | [x] | [ ] | n/a |
| I7 | Admin triggers a password reset | [x] | [ ] | n/a |
| I8 | Admin resends or revokes a pending invite | [x] | [ ] | n/a |
| M1 | Public screens are the login family only, 50/50 split, noindex everywhere | n/a | [ ] | n/a |
| M2 | Footer shows version and git SHA | n/a | [ ] | n/a |
| N1 | Skippable role-aware onboarding tour (web); three-card intro (mobile) | [ ] | [ ] | [ ] |

Notes on ticks made by the build (the owner still confirms each against the evidence):
- A3: the API refusing every role everywhere is tested (`tests/api/test_access_matrix.py`). The case of Staff opening another
  user's expense and getting 404 is tested in Pass 3, when expenses exist.
- A4: tested on the transition table for all three document types (`test_a4_...`); the approve endpoints that use it arrive in Pass 3.
- F1: the transition table and its matrix test (Pass 1).

## Cross-cutting checks (not single stories)

| Group | What to confirm | Part |
|---|---|---|
| J1 J2 J9 | [ ] Health, ready, version endpoints; correlation id in every log line; CORS, headers, secrets from environment | Backend |
| J4 J7 J10 | [ ] Migrations apply to an empty database and re-run cleanly; pooled connections; seed and reset steps documented | Backend |
| K1 K2 K3 | [ ] Seeded demo users per role with credentials on the login page (only when `DEMO_MODE` is on); realistic Pakistani data; 60-second README | Backend, Frontend |
| K4 K5 | [ ] Print stylesheet for vouchers; empty, loading and error state on every screen | Frontend |
| L1 to L4 | [ ] Voucher year setting; document date versus created time; UTC stored and sent; one display zone, identical on web and mobile; period lock | Backend |
| L5 L8 | [ ] One money format everywhere; no optimistic UI for post, void or approve | Frontend |
| L9 | [ ] Session expiry keeps the draft and the intended URL | Frontend |
| L10 | [ ] Mobile offline banner, queue, minimum version check | Mobile |
