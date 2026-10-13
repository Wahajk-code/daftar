# Build plan

The build in passes, in order. Each ended with a checkpoint: checks pass, a short report, the owner reviews. Backend first, then
the web app, then owner QA, then deploy.

| Pass | What | State |
|---|---|---|
| 1 Foundation | Docker stack, FastAPI and Next.js scaffolds, auth tokens, money and allocation, status table | Done |
| 2 Access and master data | Roles, users and invites, vendors, accounts, categories, cost centres, projects, tax rules, rate limits | Done |
| 3 Documents | Expenses, purchases, attachments (Cloudinary), approval workflow and history | Done |
| 4 Ledger | Vouchers, balance trigger, numbering, post, void, idempotency, generation from an expense or purchase, period locks | Done |
| 5 Backend completion | Email, reports and CSV, duplicate warnings, seed data, OpenAPI export, onboarding tour state | Done |
| 6 Web app | Shell, screens for all four roles, the three editors, approvals, reports, audit log, settings; two design passes after owner QA; filters, charts, search, print, exports, live validation, camera capture and install (PWA) | Done |
| 7 Hardening | Draft visibility, role redirects, security headers, accessibility and responsive checks by hand | Done, except the items below |
| 8 Deploy | Neon, Render, Vercel, Cloudinary, Google SMTP; migrations and demo data on the live database | Done; see the email note |
| 10 Submission | Docs, README, transcripts and usage, mistakes log | Done |

There is no Pass 9: the planned Expo (React Native) app was replaced by the installable web app (decision 148).

## Not done, stated plainly

- **Email from the live site.** Render's free web service blocks outbound SMTP, so the API cannot reach Google's mail server from
  there; email works locally and on a paid instance. Invitation emails are shown as screenshots instead.
- **Frontend tests.** The web app is checked by types, lint, the production build and by hand; there are no automated frontend or
  browser tests. The date helpers are not yet tested under several time zones.
- **Offline capture.** No service worker, so the camera needs a connection.
- **Content-Security-Policy**, a Python dependency audit and a keyboard-only walk through the voucher editor.
- **Full-suite run at the end.** The last full backend run passed except three tests it exposed, which were fixed and re-run
  individually; targeted runs covered later changes.

## Rules that held for every pass

- Every user story has a test or a check named with its ID (`test_e3_...`), ticked in `story-matrix.md`.
- A database rule has a test that reaches it by bypassing the service.
- Money is `Decimal` and `NUMERIC(14,2)`, never a float; division only in `core/money.py` and `core/allocation.py`.
- Nothing is deleted: master data is deactivated and posted records are reversed.
