# Domain rules

The rules the code must follow exactly. `architecture.md` says where each is enforced.

## 1. Money
- Stored as `NUMERIC(14,2)`, handled as `Decimal`, sent in JSON as a string (`"1250.00"`). Floats are refused at the boundary.
- One rounding rule (`ROUND_HALF_UP`, two places), applied once, in `core/money.py`. Division happens only there and in `core/allocation.py`.
- Percentages are integer basis points. 10,000 is 100%.
- Maximum value is `999,999,999,999.99`; the Python layer enforces it.
- Currency is PKR. A `currency` column exists on money tables so multi-currency is a migration, not a rewrite.
- One number format everywhere (web, mobile, print, CSV): `1,234,567.00`, one negative convention.

## 2. Allocation (indirect expenses)
An indirect expense is split across cost centres by percentage (basis points) or fixed amounts.
1. Convert the total to integer paisa.
2. For each bucket, `ideal = total * weight / sum(weights)`. Keep the floor.
3. Give the leftover paisa, one each, to the buckets with the largest fractional remainders.
4. Break ties by bucket id ascending, so the same cost centre receives the extra paisa on every recalculation.
5. A zero weight receives zero.

Edges: an empty list, duplicate ids, all-zero weights and a zero total raise `ValueError`. Percentages must sum to
exactly 10,000 and fixed amounts to exactly the expense, or the save is rejected. The preview endpoint reports a
shortfall instead of failing.

Properties to test: the parts sum to the total; each is within one paisa of its ideal; the result is stable under
reordering; zero stays zero; the result is idempotent; values are integers; **buckets that received a leftover
rank at or above those that did not, by remainder descending then id ascending**.

## 3. Vouchers
- Types `PV`, `RV`, `JV`. Each line has an account and exactly one of debit or credit (positive). Lines may carry
  a cost centre and a project so reports can attribute posted amounts.
- Total debit equals total credit, enforced by a deferred constraint trigger at commit.
- Lines of submitted and approved vouchers are frozen. Lines of posted vouchers never change.
- **Numbering:** `{PV|RV|JV}-{year}-{seq:04d}`. A counter row per (type, year) is incremented with
  `UPDATE ... RETURNING` inside the posting transaction. The number is assigned at Post only.
- **Void:** requires a reason; creates a reversing voucher with debits and credits swapped, linked to the original,
  posted in the same transaction, dated today (in the display zone), numbered from the same counter. A reversal cannot be
  voided. At most one reversal per voucher.
- **Generation:** from an approved expense or purchase, using the category-to-account mapping. The result is a Payment voucher: the credit goes to cash for `cash` payments and to bank otherwise. Sales tax and
  withholding payable are separate lines, never netted. For an indirect expense the net amount is split across cost
  centres with the allocation function; the tax line is not split. Generating twice from one source is blocked.
  Posting a generated voucher posts its source in the same transaction.
- **Idempotency:** `Idempotency-Key` is required on post and void. The same key and request returns the original
  result.

## 4. Periods
`closed_periods` holds inclusive date ranges; no range means open. A post, or a reversal dated in a closed range,
returns 409 `PERIOD_CLOSED`. Admins close and reopen periods, and each change is audited.

## 5. Purchases and tax
Two separate withholdings apply to one payment.
- **Sales tax withholding** depends on the supplier's registration status. For an unregistered supplier the base is
  the gross value, because no sales tax was charged.
- **Income tax withholding (section 153, Income Tax Ordinance 2001)** depends on the supplier's filer (ATL) status
  and the nature of payment. The base is the gross amount including sales tax.
- Rates are **configuration, not code**. `tax_rules` is keyed by tax type, supplier registered, supplier on the filer
  list, category and an effective date range, with no overlap. The rate and rule id resolved at the document date are
  copied onto each purchase line, so later rate changes never alter a saved document.
- Seeded rates must come with cited sources and a note that they are to be verified against the current FBR
  position; published figures differ and change with each Finance Act.
- Only the flag a tax depends on is stored on a rule: registration for sales tax, filer status for income tax. The other is held
  at false, so the no-overlap constraint can compare every rule (decision 75).
- Each line is computed on its own; the header is the exact sum of the lines. Both withholdings are deducted from the
  amount payable to the supplier. A negative payable is refused.
- Registered supplier: document kind `tax_invoice`, invoice number required. Unregistered: `purchase_memo`, with a
  visible flag on screen, in print and in CSV.
- A supplier's registration and filer flags are copied onto the purchase when it is written.
- Thresholds that exempt small annual totals per supplier are not implemented.

## 5a. Attachments
Expenses and purchases can both carry attachments (images). Each is stored once in Cloudinary and recorded in `attachments`
with the parent document, content type, size, SHA-256 and uploader.

## 6. Expenses
- Direct requires a project, a product or a cost centre (projects and products share one table with a `kind`); indirect forbids all of them. The amount is positive and gross of tax; `tax_amount`
  is informational and may not exceed the amount.
- Payment methods: `cash`, `bank_transfer`, `card`, `cheque`.
- Staff create and see only their own expenses. Nobody approves their own document.
- The type may change only while the expense is a Draft.

## 7. Dates and time

One rule for the whole system: **time is UTC everywhere except on screen, and on screen it is always one configured zone,
never the device's.**

- **Instants** (`created_at`, `submitted_at`, `approved_at`, audit and history times, tokens' expiry) are stored as
  `TIMESTAMPTZ`, handled as timezone-aware UTC, and sent in the API as ISO 8601 with `Z` (for example
  `2026-10-12T14:05:00Z`). A naive datetime is rejected at the boundary. The server, the database session and the containers all run in UTC.
  The server stamps every instant; a client never supplies one for a business event.
- **Business dates** (`document_date`, period ranges, report ranges) are calendar dates (`DATE`), sent as `YYYY-MM-DD`. They carry no
  time and no zone, and are never converted through a timezone. Converting a date is how a document ends up on the wrong day.
- **Display zone:** one IANA zone from the `DISPLAY_TIMEZONE` setting, default `Asia/Karachi` (UTC+5, no daylight saving). The API
  returns it in `GET /me`. Web and mobile both format with that zone, so the same instant reads the same on every device,
  whatever the device or browser timezone is. Setting it to `UTC` shows UTC everywhere.
- **"Today":** the current date in the display zone. It defaults new documents' `document_date` and is the date of a reversal.
- **Format, identical on web and mobile:** `12 Oct 2026` for dates, `12 Oct 2026, 14:05` for instants (24-hour), full timestamp
  with the zone abbreviation on hover or long press. Month names are written out so day and month cannot be confused.
- **Exports:** CSV dates are `YYYY-MM-DD`; instants are ISO 8601 UTC with `Z`. Both are the same for every viewer.
- **Emails** show instants in the display zone with its abbreviation.
- **Ranges:** a report from `2026-10-01` to `2026-10-31` means those calendar dates inclusive, in the display zone.
- `document_date` is the accounting date and may be back-dated; `created_at` is when the row was written. Never conflate them.
- **Offline captures** on mobile store the user's chosen `document_date` and the device's UTC instant; the server stamps its own
  `created_at` on arrival.

## 8. Duplicate detection
A purchase or expense warns, but never blocks, when it resembles another: same vendor with a similar amount and a
nearby date, the same invoice number, or the same receipt SHA-256.

## 9. CSV
Cells beginning with `=`, `+`, `-` or `@` are neutralised. Amounts are plain decimals with no thousands separators.
Files are UTF-8 with a byte-order mark so Excel reads Urdu text. Every export is audited with its filter and row count.
