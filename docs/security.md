# Security

What is protected, how, and what was checked. Short on purpose.

## Controls

| Concern | Control |
|---|---|
| Passwords | argon2id. Same answer and timing for an unknown email. Admins trigger reset emails and never see or set a password |
| Sessions | Access token 15 minutes; rotating refresh token stored hashed. Reuse of a used refresh token revokes all of that user's tokens |
| Browser | Tokens live only in HttpOnly, SameSite=Strict cookies set by the web app's server (BFF). Every write checks `Origin`. The API has no CORS, so other sites cannot call it from a browser |
| Access | A role check on every route, then an ownership check in the service. Staff see only their own expenses; a draft is invisible to Approvers until submitted; nobody approves their own document. The sidebar and a server-side redirect hide screens a role cannot use (the API is the real boundary) |
| Abuse | Named rate limits (below), counted before the password check, keyed on the email or user first, throttle never lock |
| Data | Vendor bank account encrypted and masked in every response. Reset and invite tokens hashed, single use. No tokens or bank details in logs |
| Uploads | File signature check, size and pixel caps, re-encoded (EXIF and location removed), SHA-256 stored, kept in Cloudinary as authenticated assets and served only through the API after an ownership check |
| CSV | Cells starting `= + - @` are neutralised; UTF-8 with a byte-order mark; every export is limited and audited |
| Headers | `nosniff`, no framing, referrer policy on the API and the web app; HSTS in production; camera allowed for the site only. No Content-Security-Policy yet (Next.js needs per-request nonces) |
| Config | The API refuses to start in production with debug on, a weak `SECRET_KEY`, receipts not in Cloudinary or email on the console. Its interactive documentation pages are off in production |
| Database | The app role cannot change the schema; the audit log is insert-only; money and ledger rules are held by constraints and triggers |
| Secrets | Only in `.env`, `.env.deploy` and the hosts' dashboards (all git-ignored or off the repo). The repo and the published transcripts were scanned for keys |

## Rate limits

| Policy | Key | Default |
|---|---|---|
| Login failures | email and IP / email / IP | 5 per 15 min / 30 per hour / 20 per 15 min |
| Forgot password | email / IP | 3 per hour / 10 per hour |
| Reset confirm and invite accept | IP | 10 per 15 min |
| Admin-triggered reset or invite resend | target user | 3 per hour |
| Password re-entry for a sensitive change | user | 5 per 15 min |
| Receipt uploads / CSV exports | user | 30 / 10 per hour |
| Any authenticated route | user | 300 per minute |

The client address is trusted only when the web app proves itself with the shared secret (`BFF_SHARED_SECRET`), so nobody can
spoof it. Counters live in memory, so the API runs one worker; a restart resets them.

## What was checked

- Every route by every role (`tests/api/test_access_matrix.py`), and Staff opening another user's record (404 everywhere).
- Every mutating route writes an audit row in the same transaction (`test_audit_coverage.py`).
- Parallel tests for posting, voiding, approving and idempotent retries.
- `pnpm audit --prod` on the web app: no known vulnerabilities. A Python dependency audit was not run.
- A scan of the repository history and the transcripts for keys, passwords and local paths.
- A live check: the API answers 404 for its documentation pages, and the web app redirects a role away from screens it may not use.

## Known limits

- No Content-Security-Policy and no uploaded-file virus scan (images are re-encoded, which drops anything but pixels).
- The in-memory rate limiter resets on restart and is per process. A large distributed flood needs protection in front of the host.
- Demonstration accounts share a published password. Turn `DEMO_MODE` off and change or deactivate them before real use.
- No formal third-party penetration test or code audit.
