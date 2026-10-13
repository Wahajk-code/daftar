# Story matrix

Tick each box only when you have seen the evidence yourself. B = backend test, F = screen or frontend check (the owner ticks F).

Name every test so it contains its story ID, for example `test_e3_posts_get_consecutive_numbers`.
Find the tests for a story with: `Select-String -Path backend\tests\*.py -Pattern 'test_e3_'`

| ID | Story | B | F |
|---|---|---|---|
| A1 | Sign in with email and password | [x] | [ ] |
| A2 | Admin invites users, assigns one role each, manages them | [x] | [ ] |
| A3 | UI shows permitted actions; API refuses the rest; other user's record is 404 | [x] | [ ] |
| A4 | Nobody approves their own document (all three types) | [x] | [ ] |
| B1 | Vendors with NTN, STRN, contact, bank details (masked) | [x] | [ ] |
| B2 | Separate ATL (filer) flag on vendors | [x] | [ ] |
| B3 | Chart of accounts with hierarchy; parents not postable | [x] | [ ] |
| B4 | Cost centres and projects, deactivatable | [x] | [ ] |
| B5 | Tax rules by date; rate copied onto the line | [x] | [ ] |
| C1 | Direct expense against project, product or cost centre | [x] | [ ] |
| C2 | Indirect expense allocated by percentage or fixed, exact sums | [x] | [ ] |
| C3 | Receipt attachment, validated, private, stripped | [x] | [ ] |
| C4 | Submit an expense for approval | [x] | [ ] |
| C5 | Approve or reject with a comment | [x] | [ ] |
| C6 | Post an approved expense (creates a posted voucher) | [x] | [ ] |
| C7 | Rejected expense returns to Draft for its author | [x] | [ ] |
| D1 | Purchase lines; totals recomputed on the server | [x] | [ ] |
| D2 | Registered vendor: invoice number, sales tax, both withholdings | [x] | [ ] |
| D3 | Unregistered vendor: purchase memo, visible flag, gross-value withholding | [x] | [ ] |
| D4 | Purchases use the same lifecycle as expenses | [x] | [ ] |
| D5 | Purchase and its paying voucher link both ways | [x] | [ ] |
| D6 | Attach documents to a purchase | [x] | [ ] |
| E1 | Voucher with debit and credit lines, one side per line | [x] | [ ] |
| E2 | Cannot save unbalanced; running difference; one-click balancing line | [x] | [ ] |
| E3 | Gapless numbering per type and year, assigned at Post | [x] | [ ] |
| E4 | Generate a voucher from an approved expense or purchase | [x] | [ ] |
| E5 | Post is idempotent; posted lines are immutable | [x] | [ ] |
| E6 | Void with reason creates one linked reversal | [x] | [ ] |
| F1 | One transition table; every valid and invalid pair tested | [x] | n/a |
| F2 | Approval history timeline, one component for all types | [x] | [ ] |
| F3 | Audit row for every create, update, status change | [x] | n/a |
| G1 | Expenses by type and cost centre | [x] | [ ] |
| G2 | Purchases by vendor, registered versus not | [x] | [ ] |
| G3 | Voucher register, voids linked to reversals | [x] | [ ] |
| G4 | CSV export, injection-safe, UTF-8 with BOM | [x] | [ ] |
| G5 | Activity by person: what each worker created, sent, had rejected, decided, posted and voided | [x] | [ ] |
| H1 | Camera button on a phone starts an expense from a photo, compressed | n/a | [ ] |
| H2 | Not built: capture survives a bad connection (no offline mode) | n/a | n/a |
| H3 | View and approve or reject items from the phone | n/a | [ ] |
| H4 | Vouchers readable on a phone | n/a | [ ] |
| H5 | Tokens in HttpOnly cookies, cleared on sign-out | [x] | [ ] |
| I1 | Password reset by email (self-service) | [x] | [ ] |
| I2 | Approver emailed on submission | [x] | n/a |
| I3 | Submitter emailed on approve or reject | [x] | n/a |
| I4 | Admin invites a user by email | [x] | [ ] |
| I7 | Admin triggers a password reset | [x] | [ ] |
| I8 | Admin resends or revokes a pending invite | [x] | [ ] |
| M1 | Public screens are the login family only, 50/50 split, noindex everywhere | n/a | [ ] |
| M2 | Footer shows version and git SHA | n/a | [ ] |
| N1 | Skippable role-aware onboarding tour | [x] | [ ] |

Notes on ticks made by the build (the owner still confirms each against the evidence):
- A3: the API refusing every role everywhere is tested (`tests/api/test_access_matrix.py`), and Staff opening another
  user's expense get 404 on every route (`test_a3_staff_asking_for_another_users_expense_get_a_404_everywhere`).
- A4: tested on the transition table for all three document types, and through the approve endpoints for expenses and
  purchases (`test_a4_...`, `test_d4_rejecting_needs_a_comment_and_nobody_approves_their_own_purchase`). Vouchers follow in Pass 4.
- C3 and D6: the stored file is read back through the API with the in-memory store; the live Cloudinary check waits for the credential.
- F1: the transition table and its matrix test (Pass 1).

## Cross-cutting checks (not single stories)

| Group | What to confirm | Part |
|---|---|---|
| J1 J2 J9 | [ ] Health, ready, version endpoints; correlation id in every log line; CORS, headers, secrets from environment | Backend |
| J4 J7 J10 | [ ] Migrations apply to an empty database and re-run cleanly; pooled connections; seed and reset steps documented | Backend |
| K1 K2 K3 | [ ] Seeded demo users per role with credentials on the login page (only when `DEMO_MODE` is on); realistic Pakistani data; 60-second README | Backend, Frontend |
| K4 K5 | [ ] Print stylesheet for vouchers; empty, loading and error state on every screen | Frontend |
| L1 to L4 | [ ] Voucher year setting; document date versus created time; UTC stored and sent; one display zone; period lock | Backend |
| L5 L8 | [ ] One money format everywhere; no optimistic UI for post, void or approve | Frontend |
| L9 | [ ] Session expiry keeps the draft and the intended URL | Frontend |
