# Seed data specification

`make seed` must produce a dataset a reviewer can explore for ten minutes without hitting an
empty screen. No lorem ipsum, no `Acme Corp`, no `test@example.com`.

## Accounts (four, one per role, password identical, shown on the login page)

| Email | Role | Name |
|---|---|---|
| admin@daftar.pk | admin | Nadia Qureshi |
| accounts@daftar.pk | accountant | Usman Tariq |
| approver@daftar.pk | approver | Ayesha Siddiqui |
| staff@daftar.pk | staff | Bilal Ahmed |

## Chart of accounts (minimal but real)

```
1000 Assets
  1100 Cash in Hand
  1200 Bank — Meezan Current
  1300 Advance Tax Receivable
2000 Liabilities
  2100 Accounts Payable
  2200 Sales Tax Payable
  2300 Withholding Tax Payable
3000 Equity
  3100 Owner's Capital
4000 Income
  4100 Service Revenue
5000 Expenses
  5100 Rent
  5200 Utilities
  5300 Salaries
  5400 Materials
  5500 Travel
  5600 Office Supplies
```

Parents (1000, 2000, …) are not postable.

## Cost centres and projects

Cost centres: `HO` Head Office, `OPS` Operations, `SALES` Sales, `IT` IT.
Projects: `PRJ-001` Gulberg Fit-out, `PRJ-002` NUST Campus Rollout.

## Vendors (mix of registered and not, Pakistani names)

| Name | Registered | ATL | NTN | STRN |
|---|---|---|---|---|
| Ravi Stationers | yes | yes | 1234567-8 | 03-01-8700-123-45 |
| Zarai Traders | yes | no | 7654321-2 | 03-01-8700-765-43 |
| Karachi Cables (Pvt) Ltd | yes | yes | 2233445-6 | 03-02-8700-223-34 |
| Haji Noor Transport | no | no | — | — |
| Al-Madina Printers | no | yes | 9988776-1 | — |

The last two exercise the purchase-memo path. The mismatch between registration and ATL on rows
two and five is deliberate — it proves the two flags drive different rates.

## Documents — about three months of history

- ~40 expenses spread across every status, roughly 60% direct and 40% indirect
- at least three indirect expenses whose allocation produces a rounding remainder
  (e.g. 10,000.00 split three ways; 7,500.00 split 33/33/34)
- ~15 purchases, at least four from unregistered vendors
- ~25 posted vouchers with **consecutive** numbers per type and year
- exactly one voided voucher, with its reversal visible and linked
- two documents sitting in Submitted, so the Approver login has something waiting
- one pair of near-duplicate purchases, so the duplicate-detection banner fires
- one expense just under the approval limit (49,750 against 50,000), so the round-amount flag fires

## Periods

Current month open. The two prior months closed, so `PERIOD_CLOSED` is demonstrable.

## Attachments

Three or four small generated receipt images (plain rendered text on an off-white background is
fine — they must not be stock photos). At least one shared between two expenses, so the
SHA-256 duplicate check has something to find.

## Rule

Every number visible on any screen must come from a real query against this data. If a figure
cannot be traced to a row, it does not appear.
